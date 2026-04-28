from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Optional

import numpy as np
import pandas as pd

from core.analysis.chan import ChanEngine
from core.analysis.fundamental import FundamentalEngine
from core.analysis.macro import MacroEngine
from core.analysis.orderflow import OrderFlowEngine
from core.analysis.sentiment import SentimentEngine
from core.analysis.technical import TechnicalEngine
from core.arbitration import ArbitrationEngine
from core.audit.closed_loop import DecisionRegistry, ExecutionRegistry, FeedbackRegistry, RiskAuditRegistry
from core.audit.engine import DecisionAuditor, ExecutionAuditor, RiskAuditor
from core.audit.feedback import FeedbackEngine
from core.execution import ExecutionIntent, ExecutionRuntime
from core.execution.enums import ExecutionMode as FloorExecutionMode
from core.execution.enums import OrderType as FloorOrderType
from core.execution.enums import Side as FloorSide
from core.data.live.adapters import (
    FredMacroAdapter,
    YahooFundamentalAdapter,
    YahooMarketAdapter,
    YahooNewsAdapter,
)
from core.data.live.providers import FredMacroProvider, ProviderFetchResult, YahooFinanceLiveProvider
from core.data.source_registry import (
    DataSourceProfile,
    DataSourceRegistry,
    ProviderCapabilityStatus,
)
from core.risk.engine import RiskEngine
from core.schemas import Direction, ExecutionQuality, OrderFlowSignal, Portfolio, Regime, TimeFrame, TradingSuggestion
from core.strategy_pool.interfaces.arbitration_bridge import ArbitrationInputBridge
from core.strategy_pool.schemas.arbitration_input import PortfolioProposal, StrategyProposal
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle


@dataclass(slots=True)
class ModuleRunResult:
    module: str
    status: str
    coverage_status: str
    provider: str
    adapter: str
    real_coverage: str
    input_data: list[str] = field(default_factory=list)
    latest_data_time: Optional[datetime] = None
    data_count: Optional[int] = None
    placeholder_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    payload: Any = None

    def to_public(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "status": self.status,
            "coverage_status": self.coverage_status,
            "provider": self.provider,
            "adapter": self.adapter,
            "real_coverage": self.real_coverage,
            "input_data": self.input_data,
            "latest_data_time": self.latest_data_time,
            "data_count": self.data_count,
            "output_direction": self._output_direction(),
            "confidence": self._confidence(),
            "placeholder_fields": self.placeholder_fields,
            "notes": self.notes,
            "raw_response": self._public_payload(),
        }

    def _output_direction(self) -> str:
        if self.payload is None:
            return "n/a"
        direction = getattr(self.payload, "direction", None)
        if direction is not None:
            return getattr(direction, "value", str(direction)).upper()
        if hasattr(self.payload, "equity_bias"):
            return str(getattr(self.payload, "equity_bias")).upper()
        if hasattr(self.payload, "book_imbalance"):
            imbalance = float(getattr(self.payload, "book_imbalance", 0.0))
            if imbalance > 0.05:
                return "LONG"
            if imbalance < -0.05:
                return "SHORT"
            return "FLAT"
        if hasattr(self.payload, "composite_sentiment"):
            sentiment = float(getattr(self.payload, "composite_sentiment", 0.0))
            if sentiment > 0.05:
                return "LONG"
            if sentiment < -0.05:
                return "SHORT"
            return "FLAT"
        return "n/a"

    def _confidence(self) -> Optional[float]:
        if self.payload is None:
            return None
        for attr in ("confidence", "regime_confidence", "quality_score"):
            value = getattr(self.payload, attr, None)
            if value is not None:
                return float(value)
        if hasattr(self.payload, "absorption_score"):
            return float(getattr(self.payload, "absorption_score", 0.0))
        if hasattr(self.payload, "composite_sentiment"):
            return min(abs(float(getattr(self.payload, "composite_sentiment", 0.0))), 1.0)
        return None

    def _public_payload(self) -> Any:
        if self.payload is None:
            return None
        if hasattr(self.payload, "model_dump"):
            return self.payload.model_dump(mode="json")
        if hasattr(self.payload, "__dataclass_fields__"):
            return asdict(self.payload)
        return self.payload


class LiveAnalysisOrchestrator:
    """Orchestrates real data fetch -> six modules -> Phase 6/7/8."""

    def __init__(self, profile_id: Optional[str] = None, profile: Optional[DataSourceProfile] = None) -> None:
        self.source_registry = DataSourceRegistry()
        self.profile = profile or self.source_registry.get_profile(profile_id)
        self._validate_profile()
        self.yahoo = YahooFinanceLiveProvider()
        self.fred = FredMacroProvider()
        self.market_adapter = YahooMarketAdapter()
        self.fundamental_adapter = YahooFundamentalAdapter()
        self.news_adapter = YahooNewsAdapter()
        self.macro_adapter = FredMacroAdapter()

    def _validate_profile(self) -> None:
        if not self.profile.enabled:
            raise ValueError(f"Data source profile is disabled: {self.profile.profile_id}")
        provider_ids = [
            self.profile.market_provider,
            self.profile.fundamental_provider,
            self.profile.macro_provider,
            self.profile.news_provider,
            self.profile.orderflow_provider,
            self.profile.sentiment_provider,
            self.profile.execution_provider,
        ]
        unavailable = [
            provider_id
            for provider_id in provider_ids
            if self._capability(provider_id).status == ProviderCapabilityStatus.UNAVAILABLE
        ]
        if unavailable:
            raise ValueError(f"Data source profile contains unavailable providers: {', '.join(unavailable)}")

    def _capability(self, provider_id: str):
        return self.source_registry.get_capability(provider_id)

    def _fetch_market_bars(
        self,
        *,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> ProviderFetchResult:
        if self.profile.market_provider == "yahoo_market":
            return self.yahoo.fetch_bars(symbol=symbol, interval=interval, start=start, end=end)
        cap = self._capability(self.profile.market_provider)
        raise RuntimeError(
            f"{cap.display_name} is registered as {cap.status.value}, "
            "but the live pipeline has no configured market-bar reader for this profile."
        )

    def _fetch_orderflow_bars(self, *, symbol: str, minutes: int) -> ProviderFetchResult:
        cap = self._capability(self.profile.orderflow_provider)
        if self.profile.orderflow_provider == "intraday_bars_proxy":
            return self.yahoo.fetch_recent_intraday(symbol=symbol, minutes=minutes)
        empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        return ProviderFetchResult(
            provider=cap.provider,
            payload=empty,
            notes=[f"{cap.display_name} is {cap.status.value}; orderflow uses a neutral signal."],
        )

    def _fetch_news(self, *, symbol: str, limit: int) -> ProviderFetchResult:
        cap = self._capability(self.profile.news_provider)
        if self.profile.news_provider == "yahoo_news":
            return self.yahoo.fetch_news(symbol=symbol, limit=limit)
        return ProviderFetchResult(
            provider=cap.provider,
            payload=[],
            notes=[f"{cap.display_name} is {cap.status.value}; no news payload was fetched."],
        )

    def _fetch_macro_bundle(self) -> ProviderFetchResult:
        cap = self._capability(self.profile.macro_provider)
        if self.profile.macro_provider == "fred_macro":
            return self.fred.fetch_macro_bundle()
        return ProviderFetchResult(
            provider=cap.provider,
            payload={},
            notes=[f"{cap.display_name} is {cap.status.value}; macro engine will rely on market context only."],
        )

    def _fetch_fundamentals(self, *, symbol: str) -> ProviderFetchResult:
        if self.profile.fundamental_provider == "yahoo_fundamentals":
            return self.yahoo.fetch_fundamentals(symbol=symbol)
        cap = self._capability(self.profile.fundamental_provider)
        raise RuntimeError(f"{cap.display_name} is {cap.status.value}; no real fundamentals adapter is active.")

    def _neutral_orderflow(self, symbol: str, timeframe: str, note: str) -> OrderFlowSignal:
        return OrderFlowSignal(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            timeframe=self._to_timeframe(timeframe),
            book_imbalance=0.0,
            bid_pressure=0.0,
            ask_pressure=0.0,
            delta=0.0,
            cum_delta=0.0,
            absorption_score=0.0,
            liquidity_sweep=False,
            expected_slippage=0.0,
            execution_condition=ExecutionQuality.FAIR,
            metadata={"coverage_status": "PLACEHOLDER", "reason": note},
        )

    def _to_timeframe(self, timeframe: str) -> TimeFrame:
        normalized = timeframe.lower().strip()
        mapping = {
            "1m": TimeFrame.M1,
            "5m": TimeFrame.M5,
            "15m": TimeFrame.M15,
            "30m": TimeFrame.M30,
            "1h": TimeFrame.H1,
            "4h": TimeFrame.H4,
            "1d": TimeFrame.D1,
            "1w": TimeFrame.W1,
        }
        return mapping.get(normalized, TimeFrame.D1)

    def run_live_analysis(
        self,
        symbol: str,
        timeframe: str = "1d",
        market_type: str = "auto",
        lookback: int = 180,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        news_limit: int = 10,
        profile_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if profile_id and profile_id != self.profile.profile_id:
            return LiveAnalysisOrchestrator(profile_id=profile_id).run_live_analysis(
                symbol=symbol,
                timeframe=timeframe,
                market_type=market_type,
                lookback=lookback,
                start=start,
                end=end,
                news_limit=news_limit,
            )
        end = end or datetime.now(UTC)
        start = start or self._infer_start(timeframe, lookback, end)

        modules: dict[str, ModuleRunResult] = {}

        bar_fetch = self._fetch_market_bars(symbol=symbol, interval=timeframe, start=start, end=end)
        bars = self.market_adapter.to_bars(symbol=symbol, timeframe=timeframe, frame=bar_fetch.payload).payload
        market_quote = self._build_market_quote(symbol=symbol, bars=bars, fetch=bar_fetch)
        intraday_fetch = self._fetch_orderflow_bars(symbol=symbol, minutes=max(60, min(lookback, 240)))
        intraday_bars = self.market_adapter.to_bars(
            symbol=symbol,
            timeframe="1m",
            frame=intraday_fetch.payload,
        ).payload

        technical = TechnicalEngine().analyze(bars)
        modules["technical"] = ModuleRunResult(
            module="Technical",
            status="ok",
            coverage_status="REAL",
            provider=self._capability(self.profile.market_provider).provider,
            adapter=self.market_adapter.name,
            real_coverage="real OHLCV bars / timeframe / lookback",
            input_data=["OHLCV bars", f"timeframe={timeframe}", f"lookback={lookback}"],
            latest_data_time=self._latest_timestamp(bars),
            data_count=len(bars),
            payload=technical,
        )

        chan = ChanEngine().analyze(bars)
        modules["chan"] = ModuleRunResult(
            module="Chan",
            status="ok",
            coverage_status="REAL",
            provider=self._capability(self.profile.market_provider).provider,
            adapter=self.market_adapter.name,
            real_coverage="real K-line sequence from OHLCV bars",
            input_data=["OHLCV K-line sequence", f"timeframe={timeframe}"],
            latest_data_time=self._latest_timestamp(bars),
            data_count=len(bars),
            payload=chan,
        )

        orderflow_signal = (
            OrderFlowEngine().analyze(intraday_bars)
            if self.profile.orderflow_provider == "intraday_bars_proxy"
            else self._neutral_orderflow(symbol, timeframe, f"{self.profile.orderflow_provider} is not active")
        )
        orderflow_cap = self._capability(self.profile.orderflow_provider)
        modules["orderflow"] = ModuleRunResult(
            module="OrderFlow",
            status="ok",
            coverage_status=orderflow_cap.status.value,
            provider=orderflow_cap.provider,
            adapter=orderflow_cap.adapter,
            real_coverage="real intraday market bars driving market-approx orderflow" if orderflow_cap.status == ProviderCapabilityStatus.PROXY else "not active in this profile",
            input_data=["1m intraday bars proxy"] if self.profile.orderflow_provider == "intraday_bars_proxy" else [self.profile.orderflow_provider],
            latest_data_time=self._latest_timestamp(intraday_bars),
            data_count=len(intraday_bars),
            placeholder_fields=["trade_prints", "order_book_depth"] if orderflow_cap.status != ProviderCapabilityStatus.REAL else [],
            notes=orderflow_cap.notes,
            payload=orderflow_signal,
        )

        news_items = self._fetch_news(symbol=symbol, limit=news_limit)
        news_events_result = self.news_adapter.to_news_events(symbol=symbol, raw_items=news_items.payload)
        sentiment_signal = SentimentEngine().analyze(
            {"bars": bars, "news": news_events_result.payload},
            news_events=news_events_result.payload,
        )
        sentiment_cap = self._capability(self.profile.sentiment_provider)
        modules["sentiment"] = ModuleRunResult(
            module="Sentiment",
            status="ok",
            coverage_status=sentiment_cap.status.value,
            provider=sentiment_cap.provider,
            adapter=sentiment_cap.adapter,
            real_coverage="real symbol news inputs with real market bars as auxiliary context",
            input_data=["Yahoo news", "OHLCV bars"],
            latest_data_time=self._latest_timestamp(news_events_result.payload) or self._latest_timestamp(bars),
            data_count=len(news_events_result.payload),
            placeholder_fields=news_events_result.placeholder_fields + ["social_sentiment", "forum_sentiment", "analyst_sentiment"],
            notes=sentiment_cap.notes,
            payload=sentiment_signal,
        )

        macro_payload = self._fetch_macro_bundle()
        macro_events_result = self.macro_adapter.to_macro_events(macro_payload.payload)
        macro_news_raw = []
        if self.profile.news_provider == "yahoo_news":
            for macro_symbol in ("^TNX", "^VIX"):
                try:
                    macro_news_raw.extend(self.yahoo.fetch_news(symbol=macro_symbol, limit=3).payload)
                except Exception:
                    continue
        macro_news_result = self.macro_adapter.macro_news_to_events(macro_news_raw)
        macro_events = macro_events_result.payload + macro_news_result.payload
        vix_snapshot = self.fred.fetch_vix() if self.profile.macro_provider == "fred_macro" else {
            "value": None,
            "data_status": "failed",
            "source": self._capability(self.profile.macro_provider).provider,
            "timestamp": None,
            "source_error": "vix provider not active in current profile",
            "fallback_assumption": None,
        }
        vix_level = vix_snapshot["value"]
        macro_signal = MacroEngine().analyze(
            {"bars": bars, "events": macro_events},
            macro_events=macro_events,
            vix_level=vix_level,
        )
        macro_cap = self._capability(self.profile.macro_provider)
        modules["macro"] = ModuleRunResult(
            module="Macro",
            status="ok",
            coverage_status="PROXY" if macro_events_result.placeholder_fields or macro_news_result.placeholder_fields else macro_cap.status.value,
            provider=macro_cap.provider,
            adapter=self.macro_adapter.name,
            real_coverage="real FRED macro indicators plus real Yahoo macro news converted to MacroEvent stream",
            input_data=["FRED indicators", "Yahoo macro news"],
            latest_data_time=self._latest_timestamp(macro_events),
            data_count=len(macro_events),
            placeholder_fields=macro_events_result.placeholder_fields + macro_news_result.placeholder_fields,
            notes=macro_cap.notes + macro_payload.notes,
            payload=macro_signal,
        )

        fundamental_report = None
        if self._is_equity(symbol, market_type):
            fundamentals_raw = self._fetch_fundamentals(symbol=symbol)
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
                    info=self._fetch_fundamentals(symbol=symbol).payload,
                ).payload
                if prev_bars_fetch.payload.empty:
                    prev_snapshot = None
            except Exception:
                prev_snapshot = None
            fundamental_cap = self._capability(self.profile.fundamental_provider)
            fundamental_report = FundamentalEngine().analyze(snapshot_result.payload, prev_data=prev_snapshot)
            modules["fundamental"] = ModuleRunResult(
                module="Fundamental",
                status="ok",
                coverage_status="PROXY" if snapshot_result.placeholder_fields else "REAL",
                provider=fundamental_cap.provider,
                adapter=self.fundamental_adapter.name,
                real_coverage="real Yahoo Finance fundamentals snapshot",
                input_data=["Yahoo fundamentals snapshot"],
                latest_data_time=end,
                data_count=len(fundamentals_raw.payload) if hasattr(fundamentals_raw.payload, "__len__") else None,
                placeholder_fields=snapshot_result.placeholder_fields,
                notes=fundamental_cap.notes + ["Historical YoY fields remain provider-limited unless prior period financials are available."],
                payload=fundamental_report,
            )
        else:
            modules["fundamental"] = ModuleRunResult(
                module="Fundamental",
                status="skipped",
                coverage_status="PLACEHOLDER",
                provider="n/a",
                adapter="CommodityModeSkip",
                real_coverage="not applicable for commodity/index mode",
                input_data=[f"market_type={market_type}", f"symbol={symbol}"],
                latest_data_time=None,
                data_count=0,
                notes=[f"{symbol} is treated as non-equity; fundamentals are skipped instead of proxying from OHLCV."],
                payload=None,
            )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "market_type": market_type,
            "lookback": lookback,
            "profile": self.profile,
            "start": start,
            "end": end,
            "market_quote": market_quote,
            "vix_snapshot": vix_snapshot,
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
        market_type: str = "auto",
        lookback: int = 180,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        news_limit: int = 10,
        profile_id: Optional[str] = None,
    ) -> dict[str, Any]:
        analysis = self.run_live_analysis(
            symbol=symbol,
            timeframe=timeframe,
            market_type=market_type,
            lookback=lookback,
            start=start,
            end=end,
            news_limit=news_limit,
            profile_id=profile_id,
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
        self._normalize_decision_contract(decision)

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
        risk_audit = RiskAuditor().ingest(
            plan,
            regime=(signals["technical"].regime.value if hasattr(signals["technical"].regime, "value") else str(signals["technical"].regime)),
            volatility_regime=getattr(signals["technical"], "volatility_state", None),
        )
        RiskAuditRegistry().append(risk_audit)

        execution_result = None
        execution_record = None
        if plan.execution_plan is not None and plan.final_quantity > 0 and not plan.veto_triggered:
            execution_result = self._run_execution(plan)
            execution_record = ExecutionAuditor().ingest(
                fills=self._fills_to_audit_payload(execution_result.fills),
                plan_id=plan.execution_plan.plan_id if plan.execution_plan else plan.plan_id,
                symbol=symbol,
                decision_id=decision.decision_id,
                order_type=(plan.execution_plan.algorithm.value if plan.execution_plan else "MARKET"),
                algorithm=(plan.execution_plan.algorithm.value if plan.execution_plan else "MARKET"),
                evaluator_pre_result={
                    "arrival_price": last_bar.close,
                    "estimated_slippage_bps": plan.execution_plan.estimated_slippage_bps if plan.execution_plan else 0.0,
                    "estimated_impact_bps": plan.execution_plan.estimated_impact_bps if plan.execution_plan else 0.0,
                    "estimated_fill_rate": 1.0,
                },
                evaluator_post_result={
                    "execution_quality_score": 1.0 if execution_result.report.is_complete else 0.5,
                    "quality_rating": "GOOD" if execution_result.report.is_complete else "FAIR",
                    "realized_impact_bps": float(execution_result.report.metadata.get("slippage_bps", 0.0)),
                },
                position_plan_id=plan.plan_id,
                execution_start=analysis["end"],
                execution_end=datetime.now(UTC),
            )
            ExecutionRegistry().append(execution_record)

        audited_decision = self._decision_with_signals(decision, signal_snapshots)
        audited_decision.execution_record_id = execution_record.audit_id if execution_record else None
        audited_decision.target_quantity = plan.final_quantity
        decision_record = DecisionAuditor().ingest(
            audited_decision,
            realized_pnl_pct=self._estimate_realized_pnl_pct(
                plan=plan,
                execution_record=execution_record,
                mark_price=last_bar.close,
            ),
            signal_age_hours=1.0,
            holding_period_hours=1.0,
            entry_price=(execution_record.avg_execution_price if execution_record else last_bar.close) or last_bar.close,
            exit_price=last_bar.close,
        )
        DecisionRegistry().append(decision_record)

        feedbacks = FeedbackEngine().scan(
            decision_records=[decision_record],
            execution_records=[execution_record] if execution_record else [],
            risk_audits=[risk_audit],
        )
        if feedbacks:
            FeedbackRegistry().append_many(feedbacks)

        data_status = self._build_data_status(analysis, modules)
        suggestions = self._build_suggestions(
            symbol=symbol,
            market_type=market_type,
            decision=decision,
            plan=plan,
            modules=modules,
            price=analysis["market_quote"]["price"],
            data_status=data_status,
        )
        explanation = self._build_explanation(
            decision=decision,
            plan=plan,
            modules=modules,
            suggestions=suggestions,
            data_status=data_status,
        )
        watch_plan = self._build_watch_plan(suggestions, explanation)

        return {
            **analysis,
            "decision": decision,
            "plan": plan,
            "suggestions": suggestions,
            "explanation": explanation,
            "watch_plan": watch_plan,
            "data_status": data_status,
            "decision_record": decision_record,
            "risk_audit": risk_audit,
            "execution_result": execution_result,
            "execution_record": execution_record,
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

    def _build_market_quote(self, *, symbol: str, bars: list[Any], fetch: ProviderFetchResult) -> dict[str, Any]:
        last_bar = bars[-1]
        data_status = "ok" if not fetch.notes else "degraded"
        return {
            "symbol": symbol,
            "source": fetch.provider,
            "quote_timestamp": getattr(last_bar, "timestamp", None),
            "price": float(getattr(last_bar, "close", 0.0)),
            "data_status": data_status,
            "source_diff": None,
            "source_note": " | ".join(fetch.notes) if fetch.notes else None,
        }

    def _latest_timestamp(self, rows: list[Any]) -> Optional[datetime]:
        timestamps = [getattr(row, "timestamp", None) for row in rows if getattr(row, "timestamp", None)]
        if not timestamps:
            return None
        return max(timestamps)

    def _is_equity(self, symbol: str, market_type: str = "auto") -> bool:
        normalized = (market_type or "auto").lower().strip()
        if normalized == "equity":
            return True
        if normalized in {"commodity", "crypto", "fx", "index"}:
            return False
        return all(token not in symbol for token in ("=F", "=X", "^", "-USD"))

    def _normalize_decision_contract(self, decision: Any) -> None:
        if decision.bias == "long_bias":
            decision.direction = Direction.LONG
            decision.target_direction = "LONG"
            decision.entry_permission = True
        elif decision.bias == "short_bias":
            decision.direction = Direction.SHORT
            decision.target_direction = "SHORT"
            decision.entry_permission = True
        else:
            decision.direction = Direction.FLAT
            decision.target_direction = "FLAT"
            decision.entry_permission = False

    def _build_data_status(self, analysis: dict[str, Any], modules: dict[str, ModuleRunResult]) -> dict[str, Any]:
        module_states = {
            key: {
                "coverage_status": module.coverage_status,
                "provider": module.provider,
                "adapter": module.adapter,
                "notes": module.notes,
            }
            for key, module in modules.items()
        }
        overall = "ok"
        if any(module.coverage_status in {"PROXY", "PLACEHOLDER"} for module in modules.values()):
            overall = "degraded"
        if analysis["vix_snapshot"]["data_status"] in {"degraded", "failed"}:
            overall = "degraded"
        if analysis["market_quote"]["data_status"] != "ok":
            overall = "degraded"
        return {
            "overall_status": overall,
            "quote": analysis["market_quote"],
            "vix": analysis["vix_snapshot"],
            "modules": module_states,
        }

    def _module_support_summary(self, modules: dict[str, ModuleRunResult]) -> dict[str, Any]:
        long_support: list[str] = []
        short_support: list[str] = []
        neutral_support: list[str] = []
        long_score = 0.0
        short_score = 0.0
        for module in modules.values():
            direction = (module._output_direction() or "n/a").upper()
            confidence = float(module._confidence() or 0.0)
            if direction == "LONG":
                long_support.append(module.module)
                long_score += confidence
            elif direction == "SHORT":
                short_support.append(module.module)
                short_score += confidence
            else:
                neutral_support.append(module.module)
        dominant = "neutral"
        if long_score > short_score:
            dominant = "long"
        elif short_score > long_score:
            dominant = "short"
        return {
            "long_support": long_support,
            "short_support": short_support,
            "neutral_support": neutral_support,
            "long_score": round(long_score, 4),
            "short_score": round(short_score, 4),
            "dominant_direction": dominant,
            "dominant_confidence": round(max(long_score, short_score, 0.0) / max(len(modules), 1), 4),
        }

    def _build_wti_trial_suggestion(
        self,
        *,
        symbol: str,
        price: float,
        support: dict[str, Any],
        data_status: dict[str, Any],
    ) -> Optional[TradingSuggestion]:
        if symbol != "CL=F":
            return None
        if support["dominant_direction"] not in {"long", "short"}:
            return None

        direction = "LONG" if support["dominant_direction"] == "long" else "SHORT"
        bundle = StrategySignalBundle(
            bundle_id=f"wti-bundle-{int(datetime.now(UTC).timestamp())}",
            source_strategy_id="wti_momentum",
            symbol=symbol,
            direction=direction,
            strength=min(max(support["dominant_confidence"], 0.2), 0.95),
            confidence=min(max(support["dominant_confidence"], 0.2), 0.95),
            supporting_signals=support["long_support"] if direction == "LONG" else support["short_support"],
            supporting_snapshots=["wti_market_quote", "wti_vix_context"],
            metadata={"quote": data_status["quote"], "vix": data_status["vix"]},
        )
        proposal = StrategyProposal(
            proposal_id="wti-strategy-proposal",
            strategy_id="wti_momentum",
            bundles=[bundle],
            aggregate_direction=direction,
            aggregate_strength=bundle.strength,
            aggregate_confidence=bundle.confidence,
            portfolio_weight=1.0,
        )
        portfolio = PortfolioProposal(
            proposal_id="wti-portfolio-proposal",
            portfolio_id=f"{symbol}-trial",
            proposals=[proposal],
            composite_direction=direction,
            composite_strength=bundle.strength,
            composite_confidence=bundle.confidence,
            weight_method="manual",
        )
        trial_decision = ArbitrationEngine().arbitrate_portfolio(
            ArbitrationInputBridge().build(
                portfolio_proposal=portfolio,
                supporting_factor_ids=["wti_momentum"],
                regime_context={"quote": data_status["quote"], "vix": data_status["vix"]},
            )
        )
        if trial_decision.bias not in {"long_bias", "short_bias"}:
            return None

        trial_direction = "long" if trial_decision.bias == "long_bias" else "short"
        stop_price = price * (0.97 if trial_direction == "long" else 1.03)
        take_profit = price * (1.05 if trial_direction == "long" else 0.95)
        return TradingSuggestion(
            suggestion_id=f"ts-wti-{trial_direction}",
            symbol=symbol,
            direction=trial_direction,
            grade="trial",
            confidence=trial_decision.confidence,
            reason="WTI specialized strategy-pool proposal found directional bias, but official chain did not clear risk for auto execution.",
            supporting_signals=support["long_support"] if trial_direction == "long" else support["short_support"],
            opposing_signals=support["short_support"] if trial_direction == "long" else support["long_support"],
            suggested_action="manual_review",
            entry_zone=f"{price * 0.995:.2f}-{price * 1.005:.2f}",
            invalidation_level=f"{stop_price:.2f}",
            stop_reference=f"{stop_price:.2f}",
            take_profit_reference=f"{take_profit:.2f}",
            risk_note="Trial suggestion only. It must not enter automatic execution.",
            is_executable=False,
            metadata={"strategy_id": "wti_momentum", "candidate_bias": trial_decision.bias},
        )

    def _build_suggestions(
        self,
        *,
        symbol: str,
        market_type: str,
        decision: Any,
        plan: Any,
        modules: dict[str, ModuleRunResult],
        price: float,
        data_status: dict[str, Any],
    ) -> list[dict[str, Any]]:
        support = self._module_support_summary(modules)
        suggestions: list[TradingSuggestion] = []

        if plan.final_quantity > 0 and not plan.veto_triggered and decision.bias in {"long_bias", "short_bias"}:
            direction = "long" if decision.bias == "long_bias" else "short"
            stop_price = price * (0.98 if direction == "long" else 1.02)
            take_profit = price * (1.04 if direction == "long" else 0.96)
            suggestions.append(
                TradingSuggestion(
                    suggestion_id=f"ts-official-{decision.decision_id}",
                    symbol=symbol,
                    direction=direction,
                    grade="official",
                    confidence=decision.confidence,
                    reason="Official arbitration bias passed the formal RiskEngine and produced an actionable execution plan.",
                    supporting_signals=support["long_support"] if direction == "long" else support["short_support"],
                    opposing_signals=support["short_support"] if direction == "long" else support["long_support"],
                    suggested_action=f"{plan.exec_action} {plan.final_quantity:.4f}",
                    entry_zone=f"{price * 0.9975:.2f}-{price * 1.0025:.2f}",
                    invalidation_level=f"{stop_price:.2f}",
                    stop_reference=f"{stop_price:.2f}",
                    take_profit_reference=f"{take_profit:.2f}",
                    risk_note="Executable official trade. Follow the formal risk plan and execution plan only.",
                    is_executable=True,
                    metadata={"plan_id": plan.plan_id, "decision_id": decision.decision_id},
                )
            )
        else:
            wti_trial = self._build_wti_trial_suggestion(
                symbol=symbol,
                price=price,
                support=support,
                data_status=data_status,
            )
            if wti_trial is not None:
                suggestions.append(wti_trial)
            elif support["dominant_direction"] in {"long", "short"}:
                direction = support["dominant_direction"]
                stop_price = price * (0.97 if direction == "long" else 1.03)
                take_profit = price * (1.05 if direction == "long" else 0.95)
                suggestions.append(
                    TradingSuggestion(
                        suggestion_id=f"ts-trial-{direction}-{decision.decision_id}",
                        symbol=symbol,
                        direction=direction,
                        grade="trial",
                        confidence=min(max(support["dominant_confidence"], 0.1), 0.95),
                        reason="Directional module support exists, but the official chain did not produce an executable trade.",
                        supporting_signals=support["long_support"] if direction == "long" else support["short_support"],
                        opposing_signals=support["short_support"] if direction == "long" else support["long_support"],
                        suggested_action="manual_review",
                        entry_zone=f"{price * 0.995:.2f}-{price * 1.005:.2f}",
                        invalidation_level=f"{stop_price:.2f}",
                        stop_reference=f"{stop_price:.2f}",
                        take_profit_reference=f"{take_profit:.2f}",
                        risk_note="Trial idea only. It is not executable because the formal chain did not clear.",
                        is_executable=False,
                        metadata={"decision_bias": decision.bias, "market_type": market_type},
                    )
                )

        if not suggestions:
            suggestions.append(
                TradingSuggestion(
                    suggestion_id=f"ts-watch-{decision.decision_id}",
                    symbol=symbol,
                    direction="neutral",
                    grade="watch",
                    confidence=0.0,
                    reason="No clean directional edge was confirmed by the current module mix.",
                    supporting_signals=[],
                    opposing_signals=[],
                    suggested_action="wait_for_confirmation",
                    entry_zone=None,
                    invalidation_level=None,
                    stop_reference=None,
                    take_profit_reference=None,
                    risk_note="Watch only. Wait for stronger directional alignment and a non-vetoed official decision.",
                    is_executable=False,
                    metadata={"watch_triggers": ["technical/chan alignment", "macro regime support", "risk plan becomes actionable"]},
                )
            )

        return [suggestion.model_dump(mode="json") for suggestion in suggestions]

    def _build_explanation(
        self,
        *,
        decision: Any,
        plan: Any,
        modules: dict[str, ModuleRunResult],
        suggestions: list[dict[str, Any]],
        data_status: dict[str, Any],
    ) -> dict[str, Any]:
        support = self._module_support_summary(modules)
        module_breakdown = [
            {
                "module": module.module,
                "direction": module._output_direction(),
                "confidence": module._confidence(),
                "data_status": module.coverage_status,
            }
            for module in modules.values()
        ]
        veto_check = next((check for check in plan.limit_checks if not check.passed), None)
        why_not_official = None
        if plan.veto_triggered:
            why_not_official = veto_check.details if veto_check is not None else (plan.veto_reasons[0] if plan.veto_reasons else "risk_veto")
        elif decision.bias in {"no_trade", "hold_bias"}:
            why_not_official = getattr(decision, "no_trade_reason", None) or decision.bias

        upgrade_conditions = [
            "Formal arbitration bias must be long_bias or short_bias.",
            "RiskEngine must return a non-zero quantity with no veto.",
            "Directional support should remain stronger than opposing signals.",
        ]
        if data_status["vix"]["data_status"] != "ok":
            upgrade_conditions.append("Refresh macro context once VIX data is available again.")

        return {
            "module_breakdown": module_breakdown,
            "supporting_long": support["long_support"],
            "supporting_short": support["short_support"],
            "neutral_modules": support["neutral_support"],
            "rules_applied": list(getattr(decision, "rules_applied", [])),
            "veto": {
                "triggered": bool(plan.veto_triggered),
                "reason": why_not_official,
                "filter_name": veto_check.limit_name if veto_check is not None else None,
                "mode": veto_check.mode if veto_check is not None else None,
                "raw_qty": veto_check.raw_qty if veto_check is not None else None,
                "adjusted_qty": veto_check.actual_value if veto_check is not None else None,
                "details": veto_check.details if veto_check is not None else None,
            },
            "why_not_official": why_not_official,
            "upgrade_conditions": upgrade_conditions,
            "current_suggestion_grades": [item["grade"] for item in suggestions],
        }

    def _build_watch_plan(self, suggestions: list[dict[str, Any]], explanation: dict[str, Any]) -> dict[str, Any]:
        watch_suggestion = next((item for item in suggestions if item["grade"] in {"trial", "watch"}), None)
        if watch_suggestion is None:
            return {}
        return {
            "status": "manual_follow_up",
            "primary_direction": watch_suggestion["direction"],
            "trigger_conditions": explanation["upgrade_conditions"],
            "next_action": watch_suggestion["suggested_action"],
        }

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
        data.setdefault("target_direction", getattr(decision, "target_direction", "FLAT"))
        data.setdefault("target_quantity", 0.0)
        return SimpleNamespace(**data)

    def _run_execution(self, plan) -> Any:
        import asyncio
        execution_cap = self._capability(self.profile.execution_provider)
        if self.profile.execution_provider != "simulation_execution":
            raise RuntimeError(
                f"{execution_cap.display_name} is {execution_cap.status.value}; "
                "live pipeline execution is limited to simulation_execution."
            )
        intent = self._plan_to_execution_intent(plan)

        async def _execute():
            runtime = ExecutionRuntime(mode=FloorExecutionMode.SIMULATION, venue="SIMULATED")
            await runtime.start()
            try:
                return await runtime.execute(intent)
            finally:
                await runtime.stop()

        return asyncio.run(_execute())

    def _plan_to_execution_intent(self, plan) -> ExecutionIntent:
        execution_plan = plan.execution_plan
        if execution_plan is None:
            raise RuntimeError("Execution plan is required for actionable execution")
        side = FloorSide.BUY if plan.exec_action == "BUY" else FloorSide.SELL
        order_type_map = {
            "MARKET": FloorOrderType.MARKET,
            "LIMIT": FloorOrderType.LIMIT,
            "STOP_MARKET": FloorOrderType.STOP_MARKET,
            "STOP_LIMIT": FloorOrderType.STOP_LIMIT,
            "TRAILING_STOP": FloorOrderType.TRAILING_STOP,
        }
        order_type = order_type_map.get(execution_plan.algorithm.value, FloorOrderType.MARKET)
        return ExecutionIntent(
            strategy_id="LIVE_PIPELINE",
            decision_id=plan.decision_id,
            symbol=plan.symbol,
            venue="SIMULATED",
            side=side,
            order_type=order_type,
            quantity=Decimal(str(round(plan.final_quantity, 6))),
            price=None if execution_plan.limit_price is None else Decimal(str(round(execution_plan.limit_price, 6))),
            stop_price=None if execution_plan.worst_price is None else Decimal(str(round(execution_plan.worst_price, 6))),
            metadata={
                "arrival_price": execution_plan.arrival_price or plan.current_price,
                "estimated_slippage_bps": execution_plan.estimated_slippage_bps,
                "estimated_impact_bps": execution_plan.estimated_impact_bps,
                "reference_price": plan.current_price,
                "fee_bps": max(execution_plan.estimated_impact_bps / 10, 1.0),
            },
        )

    def _fills_to_audit_payload(self, fills: list[Any]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for fill in fills:
            payload.append(
                {
                    "slice_id": getattr(fill, "record_id", ""),
                    "filled_qty": float(fill.filled_qty),
                    "fill_price": float(fill.fill_price),
                    "fill_time": fill.filled_at,
                    "slippage_bps": float(fill.metadata.get("simulated_slippage_bps", 0.0)),
                    "is_leaving_qty": False,
                    "quantity": float(fill.filled_qty),
                }
            )
        return payload

    def _estimate_realized_pnl_pct(self, *, plan, execution_record, mark_price: float) -> float:
        if execution_record is None:
            return 0.0
        entry_price = execution_record.avg_execution_price or execution_record.arrival_price or mark_price
        if entry_price <= 0:
            return 0.0
        if plan.exec_action == "SELL":
            return float((entry_price - mark_price) / entry_price)
        return float((mark_price - entry_price) / entry_price)
