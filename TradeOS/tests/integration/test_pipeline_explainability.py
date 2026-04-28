from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import tempfile

import pandas as pd

from apps.api.routers.risk import _call_risk_engine
from apps.dto.api.risk import RiskCalculateRequest
from core.data.live.orchestrator import LiveAnalysisOrchestrator
from core.data.live.providers import FredMacroProvider, ProviderFetchResult
from core.risk.context import MarketContext
from core.risk.engine import RiskEngine
from core.schemas import ArbitrationDecision, Portfolio, RiskLimits


def _portfolio(equity: float = 100_000.0) -> Portfolio:
    return Portfolio(
        timestamp=datetime.utcnow(),
        total_equity=equity,
        cash=equity,
        peak_equity=equity,
        positions=[],
    )


def _decision(bias: str, confidence: float = 0.8) -> ArbitrationDecision:
    return ArbitrationDecision(
        decision_id=f"dec-{bias}",
        timestamp=datetime.utcnow(),
        symbol="AAPL",
        bias=bias,
        confidence=confidence,
    )


def _ctx(price: float = 100.0, adv: float = 1_000_000.0, realized_vol: float = 0.20) -> MarketContext:
    return MarketContext(
        symbol="AAPL",
        timestamp=datetime.utcnow(),
        current_price=price,
        avg_daily_volume_20d=adv,
        realized_vol_20d=realized_vol,
        atr_14=2.0,
        adv_20d_usd=adv * price,
    )


def _daily_bars(start_price: float = 100.0) -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=90, freq="B", tz="UTC")
    rows = []
    price = start_price
    for i, _ in enumerate(index):
        close = price + 0.8 + (i * 0.05)
        rows.append(
            {
                "Open": price,
                "High": close + 0.6,
                "Low": price - 0.5,
                "Close": close,
                "Volume": 900_000 + i * 4_000,
            }
        )
        price = close
    return pd.DataFrame(rows, index=index)


def _intraday_bars(start_price: float = 80.0) -> pd.DataFrame:
    index = pd.date_range("2024-04-01 14:30", periods=180, freq="min", tz="UTC")
    rows = []
    price = start_price
    for i, _ in enumerate(index):
        close = price + 0.03
        rows.append(
            {
                "Open": price,
                "High": close + 0.01,
                "Low": price - 0.01,
                "Close": close,
                "Volume": 40_000 + i * 80,
            }
        )
        price = close
    return pd.DataFrame(rows, index=index)


def _macro_bundle(vix: float = 18.02) -> dict[str, pd.DataFrame]:
    dates = pd.to_datetime(["2024-03-01", "2024-04-01", "2024-05-01"], utc=True)
    return {
        "DFF": pd.DataFrame({"date": dates, "value": [5.25, 5.25, 5.00]}),
        "DGS10": pd.DataFrame({"date": dates, "value": [4.10, 4.05, 4.00]}),
        "CPIAUCSL": pd.DataFrame({"date": dates, "value": [310.0, 310.4, 310.8]}),
        "UNRATE": pd.DataFrame({"date": dates, "value": [3.9, 3.9, 3.8]}),
        "VIXCLS": pd.DataFrame({"date": dates, "value": [16.0, 15.5, vix]}),
    }


def _equity_fundamentals() -> dict:
    return {
        "marketCap": 3_000_000_000_000,
        "trailingPE": 28.0,
        "priceToBook": 12.0,
        "priceToSalesTrailing12Months": 8.0,
        "totalRevenue": 420_000_000_000,
        "ebitda": 150_000_000_000,
        "netIncomeToCommon": 98_000_000_000,
        "totalAssets": 370_000_000_000,
        "totalDebt": 100_000_000_000,
        "trailingEps": 6.5,
        "bookValue": 4.8,
        "dividendYield": 0.004,
        "beta": 1.1,
        "averageVolume": 65_000_000,
    }


def _news_payload(symbol: str) -> list[dict]:
    base = 1_712_000_000
    return [
        {
            "title": f"{symbol} trend remains constructive",
            "summary": "Demand remains firm and supply remains supportive.",
            "publisher": "Yahoo Finance",
            "providerPublishTime": base,
            "relatedTickers": [symbol],
        },
        {
            "title": f"{symbol} macro backdrop still mixed",
            "summary": "Macro commentary is mixed but does not break the trend.",
            "publisher": "Yahoo Finance",
            "providerPublishTime": base + 3600,
            "relatedTickers": [symbol],
        },
    ]


def _patch_registries(monkeypatch, tmpdir: str) -> None:
    import core.data.live.orchestrator as orchestrator_module
    from core.audit.closed_loop import DecisionRegistry, ExecutionRegistry, FeedbackRegistry, RiskAuditRegistry

    monkeypatch.setattr(
        orchestrator_module,
        "DecisionRegistry",
        lambda: DecisionRegistry(base_path=str(Path(tmpdir) / "decision")),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "RiskAuditRegistry",
        lambda: RiskAuditRegistry(base_path=str(Path(tmpdir) / "risk")),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "ExecutionRegistry",
        lambda: ExecutionRegistry(base_path=str(Path(tmpdir) / "execution")),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "FeedbackRegistry",
        lambda: FeedbackRegistry(base_path=str(Path(tmpdir) / "feedback")),
    )


class TestPhase6ToPhase7Contract:
    def test_bias_contract_reaches_risk_engine(self) -> None:
        long_plan = _call_risk_engine(
            RiskCalculateRequest(
                decision_id="risk-long",
                symbol="AAPL",
                bias="long_bias",
                confidence=0.82,
                direction="LONG",
                target_direction="LONG",
                portfolio_value=100_000.0,
                current_price=120.0,
                regime="trending_up",
            )
        )
        short_plan = _call_risk_engine(
            RiskCalculateRequest(
                decision_id="risk-short",
                symbol="AAPL",
                bias="short_bias",
                confidence=0.79,
                direction="SHORT",
                target_direction="SHORT",
                portfolio_value=100_000.0,
                current_price=120.0,
                regime="trending_down",
            )
        )
        no_trade_plan = _call_risk_engine(
            RiskCalculateRequest(
                decision_id="risk-flat",
                symbol="AAPL",
                bias="no_trade",
                confidence=0.0,
                direction="FLAT",
                target_direction="FLAT",
                no_trade_reason="arbitration_no_trade",
                portfolio_value=100_000.0,
                current_price=120.0,
                regime="unknown",
            )
        )

        assert long_plan.final_quantity > 0
        assert short_plan.final_quantity > 0
        assert no_trade_plan.final_quantity == 0.0
        assert any("arbitration_no_trade" in reason for reason in no_trade_plan.veto_reasons)


class TestRiskVetoExplainability:
    def test_filter_veto_has_reason_and_limit_check(self) -> None:
        engine = RiskEngine(risk_limits=RiskLimits(max_loss_pct_per_trade=0.01))
        plan = engine.calculate(
            decision=_decision("long_bias", confidence=0.9),
            portfolio=_portfolio(),
            market_context=_ctx(price=100.0, adv=1_000_000.0),
            avg_entry_price=50.0,
        )

        assert plan.veto_triggered is True
        assert plan.veto_reasons
        failed = [check for check in plan.limit_checks if not check.passed]
        assert failed
        assert failed[0].limit_name
        assert failed[0].mode in {"veto", "cap", "pass"}
        assert failed[0].raw_qty >= 0
        assert failed[0].actual_value >= 0
        assert failed[0].details

    def test_sizing_zero_has_explicit_reason(self) -> None:
        engine = RiskEngine()
        engine._run_sizing_chain = lambda **kwargs: {
            "qty": 0.0,
            "confidence": 0.0,
            "rationale": "all sizing methods returned 0",
            "method": "none",
        }
        plan = engine.calculate(
            decision=_decision("long_bias", confidence=0.0),
            portfolio=_portfolio(),
            market_context=_ctx(realized_vol=0.0),
        )

        assert plan.veto_triggered is True
        assert any("sizing_zero_quantity" in reason for reason in plan.veto_reasons)


class TestVixDataStatus:
    def test_vix_success_and_failure_status(self, monkeypatch) -> None:
        provider = FredMacroProvider()

        def _ok_fetch_indicator(series_id: str, lookback_rows: int = 1) -> ProviderFetchResult:
            frame = pd.DataFrame(
                {"date": pd.to_datetime(["2024-05-01"], utc=True), "value": [18.02]}
            )
            return ProviderFetchResult(provider="fred_public_csv", payload=frame, notes=[])

        monkeypatch.setattr(provider, "fetch_indicator", _ok_fetch_indicator)
        ok_result = provider.fetch_vix()
        assert ok_result["data_status"] == "ok"
        assert ok_result["value"] == 18.02
        assert ok_result["source_error"] is None

        def _fail_fetch_indicator(series_id: str, lookback_rows: int = 1) -> ProviderFetchResult:
            raise RuntimeError("FRED VIX unavailable")

        monkeypatch.setattr(provider, "fetch_indicator", _fail_fetch_indicator)
        fail_result = provider.fetch_vix(retries=0)
        assert fail_result["data_status"] in {"degraded", "failed"}
        assert fail_result["value"] is None
        assert fail_result["source_error"] == "FRED VIX unavailable"
        assert fail_result["fallback_assumption"]


class TestWtiOutput:
    def test_wti_returns_decision_suggestions_and_explanation(self, monkeypatch) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _patch_registries(monkeypatch, tmpdir)
            orchestrator = LiveAnalysisOrchestrator()
            daily = _daily_bars(start_price=76.0)
            intraday = _intraday_bars(start_price=79.0)

            monkeypatch.setattr(
                orchestrator.yahoo,
                "fetch_bars",
                lambda symbol, interval, start, end: ProviderFetchResult(
                    provider="yfinance",
                    payload=intraday.copy() if interval == "1m" else daily.copy(),
                    notes=[],
                ),
            )
            monkeypatch.setattr(
                orchestrator.yahoo,
                "fetch_recent_intraday",
                lambda symbol, minutes=120: ProviderFetchResult(
                    provider="yfinance",
                    payload=intraday.tail(minutes).copy(),
                    notes=[],
                ),
            )
            monkeypatch.setattr(
                orchestrator.yahoo,
                "fetch_news",
                lambda symbol, limit=10: ProviderFetchResult(provider="yfinance", payload=_news_payload(symbol)[:limit], notes=[]),
            )
            monkeypatch.setattr(
                orchestrator.fred,
                "fetch_macro_bundle",
                lambda: ProviderFetchResult(provider="fred_public_csv", payload=_macro_bundle(), notes=[]),
            )
            monkeypatch.setattr(
                orchestrator.fred,
                "fetch_vix",
                lambda retries=2: {
                    "value": 18.02,
                    "data_status": "ok",
                    "source": "fred_public_csv",
                    "timestamp": datetime(2024, 5, 1, tzinfo=UTC),
                    "source_error": None,
                    "fallback_assumption": None,
                },
            )

            result = orchestrator.run_live_pipeline(
                symbol="CL=F",
                market_type="commodity",
                timeframe="1d",
                lookback=60,
                start=datetime(2024, 1, 2, tzinfo=UTC),
                end=datetime(2024, 5, 1, tzinfo=UTC),
                news_limit=5,
            )

            assert result["decision"] is not None
            assert result["suggestions"]
            assert result["explanation"]["module_breakdown"]
            grades = {item["grade"] for item in result["suggestions"]}
            if "official" not in grades:
                assert grades & {"trial", "watch"}
                assert all(item["is_executable"] is False for item in result["suggestions"])
            assert result["data_status"]["quote"]["symbol"] == "CL=F"
            assert result["data_status"]["quote"]["source"] == "yfinance"
            assert result["data_status"]["vix"]["data_status"] == "ok"


class TestFullPipelineExplainability:
    def test_full_pipeline_includes_suggestions_and_audit(self, monkeypatch) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _patch_registries(monkeypatch, tmpdir)
            orchestrator = LiveAnalysisOrchestrator()
            daily = _daily_bars(start_price=120.0)
            intraday = _intraday_bars(start_price=200.0)

            monkeypatch.setattr(
                orchestrator.yahoo,
                "fetch_bars",
                lambda symbol, interval, start, end: ProviderFetchResult(
                    provider="yfinance",
                    payload=intraday.copy() if interval == "1m" else daily.copy(),
                    notes=[],
                ),
            )
            monkeypatch.setattr(
                orchestrator.yahoo,
                "fetch_recent_intraday",
                lambda symbol, minutes=120: ProviderFetchResult(
                    provider="yfinance",
                    payload=intraday.tail(minutes).copy(),
                    notes=[],
                ),
            )
            monkeypatch.setattr(
                orchestrator.yahoo,
                "fetch_fundamentals",
                lambda symbol: ProviderFetchResult(provider="yfinance", payload=_equity_fundamentals(), notes=[]),
            )
            monkeypatch.setattr(
                orchestrator.yahoo,
                "fetch_news",
                lambda symbol, limit=10: ProviderFetchResult(provider="yfinance", payload=_news_payload(symbol)[:limit], notes=[]),
            )
            monkeypatch.setattr(
                orchestrator.fred,
                "fetch_macro_bundle",
                lambda: ProviderFetchResult(provider="fred_public_csv", payload=_macro_bundle(), notes=[]),
            )
            monkeypatch.setattr(
                orchestrator.fred,
                "fetch_vix",
                lambda retries=2: {
                    "value": 18.02,
                    "data_status": "ok",
                    "source": "fred_public_csv",
                    "timestamp": datetime(2024, 5, 1, tzinfo=UTC),
                    "source_error": None,
                    "fallback_assumption": None,
                },
            )

            result = orchestrator.run_live_pipeline(
                symbol="AAPL",
                market_type="equity",
                timeframe="1d",
                lookback=60,
                start=datetime(2024, 1, 2, tzinfo=UTC),
                end=datetime(2024, 5, 1, tzinfo=UTC),
                news_limit=5,
            )

            assert result["decision"] is not None
            assert result["plan"] is not None
            assert result["suggestions"]
            assert result["explanation"]["module_breakdown"]
            assert result["risk_audit"].audit_id
            assert result["decision_record"].audit_id
            if result["execution_record"] is not None:
                assert result["execution_record"].audit_id
