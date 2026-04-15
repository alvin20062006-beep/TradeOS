from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Optional

import numpy as np

from core.analysis.chan import ChanEngine
from core.analysis.fundamental import FundamentalEngine
from core.analysis.macro import MacroEngine
from core.analysis.orderflow import OrderFlowEngine
from core.analysis.sentiment import SentimentEngine
from core.analysis.technical import TechnicalEngine
from core.arbitration import ArbitrationEngine
from core.audit.closed_loop import DecisionRegistry, FeedbackRegistry, RiskAuditRegistry
from core.audit.engine import DecisionAuditor, RiskAuditor
from core.audit.feedback import FeedbackEngine
from core.data.live.adapters import (
    FredMacroAdapter,
    YahooFundamentalAdapter,
    YahooMarketAdapter,
    YahooNewsAdapter,
)
from core.data.live.providers import FredMacroProvider, YahooFinanceLiveProvider
from core.risk.engine import RiskEngine
from core.schemas import Direction, Portfolio, Regime


@dataclass(slots=True)
class ModuleRunResult:
    module: str
    status: str
    provider: str
    adapter: str
    real_coverage: str
    placeholder_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    payload: Any = None

    def to_public(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "status": self.status,
            "provider": self.provider,
            "adapter": self.adapter,
            "real_coverage": self.real_coverage,
            "placeholder_fields": self.placeholder_fields,
            "notes": self.notes,
        }


class LiveAnalysisOrchestrator:
    """Orchestrates real data fetch -> six modules -> Phase 6/7/8."""

    def __init__(self) -> None:
        self.yahoo = YahooFinanceLiveProvider()
        self.fred = FredMacroProvider()
        self.market_adapter = YahooMarketAdapter()
        self.fundamental_adapter = YahooFundamentalAdapter()
        self.news_adapter = YahooNewsAdapter()
        self.macro_adapter = FredMacroAdapter()

    def run_live_analysis(
        self,
        symbol: str,
        timeframe: str = "1d",
        lookback: int = 180,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        news_limit: int = 10,
    ) -> dict[str, Any]:
        end = end or datetime.now(UTC)
        start = start or self._infer_start(timeframe, lookback, end)

        modules: dict[str, ModuleRunResult] = {}

        bar_fetch = self.yahoo.fetch_bars(symbol=symbol, interval=timeframe, start=start, end=end)
        bars = self.market_adapter.to_bars(symbol=symbol, timeframe=timeframe, frame=bar_fetch.payload).payload
        intraday_fetch = self.yahoo.fetch_recent_intraday(symbol=symbol, minutes=max(60, min(lookback, 240)))
        intraday_bars = self.market_adapter.to_bars(
            symbol=symbol,
            timeframe="1m",
            frame=intraday_fetch.payload,
        ).payload

        technical = TechnicalEngine().analyze(bars)
        modules["technical"] = ModuleRunResult(
            module="Technical",
            status="ok",
            provider=bar_fetch.provider,
            adapter=self.market_adapter.name,
            real_coverage="real OHLCV bars / timeframe / lookback",
            payload=technical,
        )

        chan = ChanEngine().analyze(bars)
        modules["chan"] = ModuleRunResult(
            module="Chan",
            status="ok",
            provider=bar_fetch.provider,
            adapter=self.market_adapter.name,
            real_coverage="real K-line sequence from OHLCV bars",
            payload=chan,
        )

        orderflow_signal = OrderFlowEngine().analyze(intraday_bars)
        modules["orderflow"] = ModuleRunResult(
            module="OrderFlow",
            status="ok",
            provider=intraday_fetch.provider,
            adapter=self.market_adapter.name,
            real_coverage="real intraday market bars driving market-approx orderflow",
            placeholder_fields=["trade_prints", "order_book_depth"],
            notes=[
                "Real trade prints are not available from the current provider path.",
                "Depth-of-book remains missing and is explicitly flagged.",
            ],
            payload=orderflow_signal,
        )

        news_items = self.yahoo.fetch_news(symbol=symbol, limit=news_limit)
        news_events_result = self.news_adapter.to_news_events(symbol=symbol, raw_items=news_items.payload)
        sentiment_signal = SentimentEngine().analyze(
            {"bars": bars, "news": news_events_result.payload},
            news_events=news_events_result.payload,
        )
        modules["sentiment"] = ModuleRunResult(
            module="Sentiment",
            status="ok",
            provider=news_items.provider,
            adapter=self.news_adapter.name,
            real_coverage="real symbol news inputs with real market bars as auxiliary context",
            placeholder_fields=news_events_result.placeholder_fields + ["social_sentiment", "forum_sentiment", "analyst_sentiment"],
            notes=["Sentiment scores are derived from real Yahoo Finance news headlines and summaries."],
            payload=sentiment_signal,
        )

        macro_payload = self.fred.fetch_macro_bundle()
        macro_events_result = self.macro_adapter.to_macro_events(macro_payload.payload)
        macro_news_raw = []
        for macro_symbol in ("^TNX", "^VIX"):
            try:
                macro_news_raw.extend(self.yahoo.fetch_news(symbol=macro_symbol, limit=3).payload)
            except Exception:
                continue
        macro_news_result = self.macro_adapter.macro_news_to_events(macro_news_raw)
        macro_events = macro_events_result.payload + macro_news_result.payload
        vix_level = self._extract_macro_actual(macro_events_result.payload, "CBOE VIX")
        macro_signal = MacroEngine().analyze(
            {"bars": bars, "events": macro_events},
            macro_events=macro_events,
            vix_level=vix_level,
        )
        modules["macro"] = ModuleRunResult(
            module="Macro",
            status="ok",
            provider=macro_payload.provider,
            adapter=self.macro_adapter.name,
            real_coverage="real FRED macro indicators plus real Yahoo macro news converted to MacroEvent stream",
            placeholder_fields=macro_events_result.placeholder_fields + macro_news_result.placeholder_fields,
            notes=macro_payload.notes,
            payload=macro_signal,
        )

        fundamental_report = None
        if self._is_equity(symbol):
            fundamentals_raw = self.yahoo.fetch_fundamentals(symbol=symbol)
            snapshot_result = self.fundamental_adapter.to_snapshot(symbol=symbol, info=fundamentals_raw.payload)
            prev_snapshot = None
            try:
                prev_bars_fetch = self.yahoo.fetch_bars(
                    symbol=symbol,
                    interval="1d",
                    start=end - timedelta(days=730),
                    end=end - timedelta(days=365),
                )
                prev_snapshot = self.fundamental_adapter.to_snapshot(
                    symbol=symbol,
                    info=self.yahoo.fetch_fundamentals(symbol=symbol).payload,
                ).payload
                if prev_bars_fetch.payload.empty:
                    prev_snapshot = None
            except Exception:
                prev_snapshot = None
            fundamental_report = FundamentalEngine().analyze(snapshot_result.payload, prev_data=prev_snapshot)
            modules["fundamental"] = ModuleRunResult(
                module="Fundamental",
                status="ok",
                provider=fundamentals_raw.provider,
                adapter=self.fundamental_adapter.name,
                real_coverage="real Yahoo Finance fundamentals snapshot",
                placeholder_fields=snapshot_result.placeholder_fields,
                notes=["Historical YoY fields remain provider-limited unless prior period financials are available."],
                payload=fundamental_report,
            )
        else:
            modules["fundamental"] = ModuleRunResult(
                module="Fundamental",
                status="skipped",
                provider="n/a",
                adapter="CommodityModeSkip",
                real_coverage="not applicable for commodity/index mode",
                notes=[f"{symbol} is treated as non-equity; fundamentals are skipped instead of proxying from OHLCV."],
                payload=None,
            )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "lookback": lookback,
            "start": start,
            "end": end,
            "bars": bars,
            "intraday_bars": intraday_bars,
            "news_events": news_events_result.payload,
            "macro_events": macro_events_result.payload,
            "macro_news_events": macro_news_result.payload,
            "modules": modules,
            "signals": {
                "technical": technical,
                "chan": chan,
                "orderflow": orderflow_signal,
                "sentiment": sentiment_signal,
                "macro": macro_signal,
                "fundamental": fundamental_report,
            },
        }

    def run_live_pipeline(
        self,
        symbol: str,
        timeframe: str = "1d",
        lookback: int = 180,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        news_limit: int = 10,
    ) -> dict[str, Any]:
        analysis = self.run_live_analysis(
            symbol=symbol,
            timeframe=timeframe,
            lookback=lookback,
            start=start,
            end=end,
            news_limit=news_limit,
        )
        signals = analysis["signals"]
        modules = analysis["modules"]

        decision = ArbitrationEngine().arbitrate(
            symbol=symbol,
            timestamp=analysis["end"],
            technical=signals["technical"],
            chan=signals["chan"],
            orderflow=signals["orderflow"],
            sentiment=signals["sentiment"],
            macro=signals["macro"],
            fundamental=signals["fundamental"],
        )

        last_bar = analysis["bars"][-1]
        closes = np.array([bar.close for bar in analysis["bars"]], dtype=float)
        returns = np.diff(closes) / closes[:-1] if len(closes) > 1 else np.array([0.0])
        realized_vol = float(np.std(returns[-20:]) * np.sqrt(252)) if len(returns) else 0.0
        avg_volume = float(np.mean([bar.volume for bar in analysis["bars"][-20:]]))

        portfolio = Portfolio(
            timestamp=datetime.now(UTC),
            total_equity=100000.0,
            cash=100000.0,
            peak_equity=100000.0,
            positions=[],
        )
        risk_engine = RiskEngine()
        plan = risk_engine.calculate(
            decision=decision,
            portfolio=portfolio,
            current_price=last_bar.close,
            avg_daily_volume_20d=avg_volume,
            realized_vol_20d=realized_vol,
            bid_ask_spread_bps=max(1.0, abs(signals["orderflow"].expected_slippage)),
            market_cap=signals["fundamental"].market_cap if signals["fundamental"] else 0.0,
            vix_level=signals["macro"].vix_level,
            regime_name=(signals["technical"].regime.value if hasattr(signals["technical"].regime, "value") else str(signals["technical"].regime)),
        )

        signal_snapshots = self._build_signal_snapshots(signals, modules)
        decision_record = DecisionAuditor().ingest(
            self._decision_with_signals(decision, signal_snapshots),
            entry_price=last_bar.close,
        )
        DecisionRegistry().append(decision_record)
        risk_audit = RiskAuditor().ingest(
            plan,
            regime=(signals["technical"].regime.value if hasattr(signals["technical"].regime, "value") else str(signals["technical"].regime)),
            volatility_regime=getattr(signals["technical"], "volatility_state", None),
        )
        RiskAuditRegistry().append(risk_audit)

        feedbacks = FeedbackEngine().scan(
            decision_records=[decision_record],
            execution_records=[],
            risk_audits=[risk_audit],
        )
        if feedbacks:
            FeedbackRegistry().append_many(feedbacks)

        return {
            **analysis,
            "decision": decision,
            "plan": plan,
            "decision_record": decision_record,
            "risk_audit": risk_audit,
            "feedbacks": feedbacks,
        }

    def _infer_start(self, timeframe: str, lookback: int, end: datetime) -> datetime:
        multiplier = {
            "1m": timedelta(minutes=lookback + 5),
            "5m": timedelta(minutes=lookback * 5 + 60),
            "15m": timedelta(minutes=lookback * 15 + 120),
            "30m": timedelta(minutes=lookback * 30 + 240),
            "1h": timedelta(hours=lookback + 24),
            "4h": timedelta(hours=lookback * 4 + 48),
            "1d": timedelta(days=lookback + 30),
            "1w": timedelta(weeks=lookback + 8),
        }
        return end - multiplier.get(timeframe, timedelta(days=lookback + 30))

    def _extract_macro_actual(self, events: list[Any], event_name: str) -> Optional[float]:
        for event in events:
            if getattr(event, "event_name", "") == event_name:
                return getattr(event, "actual", None)
        return None

    def _is_equity(self, symbol: str) -> bool:
        return all(token not in symbol for token in ("=F", "=X", "^", "-USD"))

    def _build_signal_snapshots(self, signals: dict[str, Any], modules: dict[str, ModuleRunResult]) -> list[SimpleNamespace]:
        snapshots: list[SimpleNamespace] = []
        for key, signal in signals.items():
            if signal is None:
                continue
            snapshots.append(
                SimpleNamespace(
                    source_module=key,
                    signal_type=type(signal).__name__,
                    direction=getattr(getattr(signal, "direction", None), "value", getattr(signal, "direction", "neutral")),
                    confidence=float(
                        getattr(
                            signal,
                            "confidence",
                            getattr(signal, "composite_sentiment", getattr(signal, "regime_confidence", 0.0)),
                        )
                    ),
                    regime=getattr(getattr(signal, "regime", None), "value", getattr(signal, "regime", None)),
                    score=getattr(signal, "entry_score", getattr(signal, "composite_sentiment", None)),
                    metadata={"module_status": modules[key].to_public()},
                )
            )
        return snapshots

    def _decision_with_signals(self, decision: Any, signals: list[SimpleNamespace]) -> SimpleNamespace:
        data = decision.model_dump() if hasattr(decision, "model_dump") else dict(decision)
        data["signals"] = signals
        data.setdefault("target_direction", data.get("bias", "no_trade"))
        data.setdefault("target_quantity", 0.0)
        return SimpleNamespace(**data)
