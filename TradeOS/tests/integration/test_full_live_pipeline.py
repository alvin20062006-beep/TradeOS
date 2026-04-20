"""Integration test for the full backend live pipeline with simulation execution."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import tempfile

import pandas as pd

from core.arbitration import ArbitrationEngine
from core.audit.closed_loop import DecisionRegistry, ExecutionRegistry, FeedbackRegistry, RiskAuditRegistry
from core.audit.feedback.engine import FeedbackEngine
from core.data.live.orchestrator import LiveAnalysisOrchestrator
from core.data.live.providers import ProviderFetchResult
from core.strategy_pool.interfaces.arbitration_bridge import ArbitrationInputBridge
from core.strategy_pool.schemas.arbitration_input import PortfolioProposal, StrategyProposal
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle


def _daily_bars() -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=90, freq="B", tz="UTC")
    rows = []
    price = 100.0
    for i, ts in enumerate(index):
        close = price + 1.2 + (i * 0.15)
        rows.append(
            {
                "Open": price,
                "High": close + 0.8,
                "Low": price - 0.6,
                "Close": close,
                "Volume": 1_000_000 + i * 5_000,
            }
        )
        price = close
    return pd.DataFrame(rows, index=index)


def _intraday_bars() -> pd.DataFrame:
    index = pd.date_range("2024-04-01 14:30", periods=180, freq="min", tz="UTC")
    rows = []
    price = 210.0
    for i, ts in enumerate(index):
        close = price + 0.05
        rows.append(
            {
                "Open": price,
                "High": close + 0.02,
                "Low": price - 0.02,
                "Close": close,
                "Volume": 50_000 + i * 100,
            }
        )
        price = close
    return pd.DataFrame(rows, index=index)


def _fundamental_info() -> dict:
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
            "title": f"{symbol} beats estimates on strong growth",
            "summary": "Revenue growth and margin expansion remain solid.",
            "publisher": "Yahoo Finance",
            "providerPublishTime": base,
            "relatedTickers": [symbol],
        },
        {
            "title": f"{symbol} receives upgrade after record demand",
            "summary": "Analysts cited strong demand and positive product mix.",
            "publisher": "Yahoo Finance",
            "providerPublishTime": base + 3600,
            "relatedTickers": [symbol],
        },
    ]


def _macro_bundle() -> dict[str, pd.DataFrame]:
    dates = pd.to_datetime(["2024-03-01", "2024-04-01", "2024-05-01"], utc=True)
    return {
        "DFF": pd.DataFrame({"date": dates, "value": [5.25, 5.25, 5.00]}),
        "DGS10": pd.DataFrame({"date": dates, "value": [4.10, 4.05, 4.00]}),
        "CPIAUCSL": pd.DataFrame({"date": dates, "value": [310.0, 310.4, 310.8]}),
        "UNRATE": pd.DataFrame({"date": dates, "value": [3.9, 3.9, 3.8]}),
        "VIXCLS": pd.DataFrame({"date": dates, "value": [16.0, 15.5, 14.0]}),
    }


class TestFullLivePipeline:
    def test_full_live_pipeline(self, monkeypatch) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            decision_registry = DecisionRegistry(base_path=str(Path(tmpdir) / "decision"))
            risk_registry = RiskAuditRegistry(base_path=str(Path(tmpdir) / "risk"))
            execution_registry = ExecutionRegistry(base_path=str(Path(tmpdir) / "execution"))
            feedback_registry = FeedbackRegistry(base_path=str(Path(tmpdir) / "feedback"))

            import core.data.live.orchestrator as orchestrator_module

            monkeypatch.setattr(orchestrator_module, "DecisionRegistry", lambda: decision_registry)
            monkeypatch.setattr(orchestrator_module, "RiskAuditRegistry", lambda: risk_registry)
            monkeypatch.setattr(orchestrator_module, "ExecutionRegistry", lambda: execution_registry)
            monkeypatch.setattr(orchestrator_module, "FeedbackRegistry", lambda: feedback_registry)

            orchestrator = LiveAnalysisOrchestrator()
            daily = _daily_bars()
            intraday = _intraday_bars()

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
                lambda symbol: ProviderFetchResult(provider="yfinance", payload=_fundamental_info(), notes=[]),
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

            last_result = None
            for _ in range(30):
                last_result = orchestrator.run_live_pipeline(
                    symbol="AAPL",
                    timeframe="1d",
                    lookback=60,
                    start=datetime(2024, 1, 2, tzinfo=UTC),
                    end=datetime(2024, 5, 1, tzinfo=UTC),
                    news_limit=5,
                )

            assert last_result is not None
            assert last_result["decision"].bias in {"long_bias", "hold_bias", "short_bias", "reduce_risk", "exit_bias", "no_trade"}
            assert last_result["plan"].execution_plan is not None
            assert last_result["execution_result"].report.is_complete
            assert last_result["execution_record"].total_filled_qty > 0

            decision_records = decision_registry.read_all(symbol="AAPL")
            risk_audits = risk_registry.read_all(symbol="AAPL")
            execution_records = execution_registry.read_all(symbol="AAPL")

            assert len(decision_records) == 30
            assert len(risk_audits) == 30
            assert len(execution_records) == 30

            feedbacks = FeedbackEngine().scan(
                decision_records=decision_records,
                execution_records=execution_records,
                risk_audits=risk_audits,
            )
            feedback_registry.append_many(feedbacks)
            assert len(feedbacks) >= 1
            assert len(feedback_registry.read_unprocessed()) >= 1

            bundle = StrategySignalBundle(
                bundle_id="bundle-1",
                source_strategy_id="trend-alpha",
                symbol="AAPL",
                direction="LONG",
                strength=0.9,
                confidence=0.85,
                supporting_signals=[decision_records[0].audit_id],
                supporting_snapshots=["alpha-factor-1"],
            )
            strategy_proposal = StrategyProposal(
                proposal_id="proposal-1",
                strategy_id="trend-alpha",
                bundles=[bundle],
                aggregate_direction="LONG",
                aggregate_strength=0.9,
                aggregate_confidence=0.85,
                portfolio_weight=1.0,
            )
            portfolio_proposal = PortfolioProposal(
                proposal_id="portfolio-proposal-1",
                portfolio_id="AAPL-portfolio",
                proposals=[strategy_proposal],
                composite_direction="LONG",
                composite_strength=0.9,
                composite_confidence=0.85,
                weight_method="manual",
            )
            arb_bundle = ArbitrationInputBridge().build(
                portfolio_proposal=portfolio_proposal,
                supporting_factor_ids=["alpha-factor-1"],
                regime_context={"regime": "trending_up"},
            )
            portfolio_decision = ArbitrationEngine().arbitrate_portfolio(arb_bundle)

            assert portfolio_decision.symbol == "AAPL"
            assert portfolio_decision.signal_count >= 1
            assert any(item.signal_name.startswith("strategy_pool:") for item in portfolio_decision.rationale)
