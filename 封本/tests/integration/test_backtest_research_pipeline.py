"""
tests/integration/test_backtest_research_pipeline.py
=================================================
Research-layer end-to-end integration test.

Pipeline: factor -> optimizer -> backtest -> evaluator metrics

Scope (THIS file)
-----------------
- factor predictions (mock)
- portfolio optimization
- backtest simulation
- evaluator metrics aggregation

NOT in scope (Phase 3 / execution layer)
-----------------------------------------
- NautilusTrader execution
- Order / Fill / ExecutionReport
- Live order routing
- Execution latency simulation

This test does NOT import from core.execution or NautilusTrader.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from core.research.backtest.engine import BacktestEngine
from core.research.backtest.evaluator import BacktestEvaluator
from core.research.backtest.schema import BacktestConfig, CostModelConfig
from core.research.backtest.cost_model import CostModel
from core.research.portfolio.optimizer import PortfolioOptimizer
from core.research.portfolio.schema import OptimizationRequest
from core.research.portfolio.schema import ConstraintConfig
from core.research.strategy.base import StrategyBase
from core.research.strategy.signal import SignalDirection, StrategySignal


# ── Dummy strategy (momentum) ────────────────────────────────────────────────

class MomentumStrategy(StrategyBase):
    """Equal-weight momentum: top half long, bottom half zero."""

    def __init__(self, n_top: int = 5):
        super().__init__(name="momentum", description="Top-n equal weight")
        self.n_top = n_top

    def generate_weights(self, timestamp, features):
        scores = features["score"] if "score" in features.columns else features.iloc[:, 0]
        top_assets = scores.nlargest(self.n_top).index
        n = len(top_assets)
        w = pd.Series(0.0, index=features.index)
        w.loc[top_assets] = 1.0 / n
        return w


# ── Test data fixtures ───────────────────────────────────────────────────────

def _make_price_df(assets, dates):
    """Generate random price series (100 base, small random walk)."""
    np.random.seed(42)
    n = len(dates)
    price_data = {}
    for asset in assets:
        base = 100.0 * np.random.uniform(0.8, 1.2)
        returns = np.random.normal(0.0005, 0.015, n)
        prices = base * np.exp(np.cumsum(returns))
        price_data[asset] = prices
    return pd.DataFrame(price_data, index=dates)


def _make_factor_df(assets, dates):
    """Generate factor scores correlated with future returns."""
    np.random.seed(42)
    n = len(dates)
    factor_data = {}
    for asset in assets:
        factor_data[asset] = np.random.randn(n)
    return pd.DataFrame(factor_data, index=dates)


# ── Integration tests ────────────────────────────────────────────────────────

class TestBacktestResearchPipeline:
    """Full pipeline: factor -> optimizer -> backtest -> evaluator."""

    @pytest.fixture
    def assets(self):
        return ["AAPL", "GOOG", "MSFT", "AMZN", "TSLA"]

    @pytest.fixture
    def dates(self):
        return pd.date_range("2024-01-01", periods=60, freq="B")

    @pytest.fixture
    def price_df(self, assets, dates):
        return _make_price_df(assets, dates)

    @pytest.fixture
    def factor_df(self, assets, dates):
        return _make_factor_df(assets, dates)

    def test_pipeline_factor_to_backtest(self, assets, dates, price_df, factor_df):
        """
        Full pipeline:
        1. Generate weights from factor (no optimizer in this path)
        2. BacktestEngine: weights + prices -> BacktestResult
        3. Evaluator: BacktestResult -> all metrics
        """
        strategy = MomentumStrategy(n_top=3)

        # Step 1: Generate weight series
        features_by_date = {
            d: factor_df.loc[[d]].T  # transpose: assets as rows
            for d in dates
        }
        # Build weight series aligned to dates
        rows = []
        for d in dates:
            feat = pd.DataFrame({"score": factor_df.loc[d]}, index=assets).T
            w = strategy.generate_weights(d, feat)
            rows.append(w)
        weights_df = pd.DataFrame(rows, index=dates).fillna(0.0)
        # Ensure columns exist
        for a in assets:
            if a not in weights_df.columns:
                weights_df[a] = 0.0
        weights_df = weights_df[assets]

        # Step 2: Backtest
        config = BacktestConfig(
            rebalance_freq="W",
            initial_capital=100_000.0,
            cost_model=CostModelConfig(fixed_bps=5.0),
            risk_free_rate=0.04,
        )
        engine = BacktestEngine(config, weights_df, price_df)
        result = engine.run(run_id="test_bt_001")

        # Verify BacktestResult fields
        assert len(result.returns_series) > 0
        assert len(result.equity_curve) > 0
        assert result.positions_series.shape[1] == len(assets)
        assert len(result.turnover_series) > 0
        assert len(result.transaction_cost_series) > 0
        assert set(result.returns_series.index) <= set(dates)
        assert result.metrics["total_return"] is not None
        assert result.metrics["sharpe_ratio"] is not None
        assert result.metadata["run_id"] == "test_bt_001"
        assert result.metadata["n_rebalance_periods"] > 0

        # Step 3: Evaluator
        evaluator = BacktestEvaluator(risk_free_rate=0.04)
        all_metrics = evaluator.evaluate(result)

        assert "bt_total_return" in all_metrics
        assert "bt_sharpe_ratio" in all_metrics
        assert "bt_max_drawdown" in all_metrics
        assert "bt_avg_turnover" in all_metrics

    def test_pipeline_optimizer_to_backtest(self, assets, dates, price_df):
        """
        Pipeline: optimizer -> backtest
        1. Build OptimizationRequest (min_variance)
        2. PortfolioOptimizer -> OptimizationResult
        3. BacktestEngine with optimizer weights -> BacktestResult
        """
        # Price returns
        returns_df = price_df.pct_change().iloc[1:]

        # Use last 20 days to build covariance matrix
        cov_df = returns_df.iloc[-20:].cov()
        mu = returns_df.iloc[-20:].mean()

        req = OptimizationRequest(
            expected_returns=mu,
            covariance_matrix=cov_df,
            objective="min_variance",
            constraints=[
                ConstraintConfig(type="sum_to_one"),
                ConstraintConfig(type="long_only"),
            ],
        )
        optimizer = PortfolioOptimizer()
        opt_result = optimizer.optimize(req)

        assert opt_result.weights is not None
        assert len(opt_result.weights) == len(assets)
        assert opt_result.solver_status == "optimal"

        # Build weight series (static weights, no rebalancing)
        # For the optimizer path: use same weights all periods
        w = opt_result.weights
        weights_df = pd.DataFrame(
            [w.values] * len(dates),
            index=dates,
            columns=w.index,
        )

        # Backtest
        config = BacktestConfig(
            rebalance_freq="W",
            initial_capital=100_000.0,
            cost_model=CostModelConfig(fixed_bps=5.0, slippage_bps=0.5),
            risk_free_rate=0.0,
        )
        engine = BacktestEngine(config, weights_df, price_df)
        result = engine.run(run_id="test_opt_001")

        assert result.returns_series is not None
        assert result.metadata["n_rebalance_periods"] > 0

    def test_backtest_with_benchmark(self, assets, dates, price_df):
        """Test backtest with benchmark weights for relative metrics."""
        strategy = MomentumStrategy(n_top=3)
        dates_trade = dates[5:]  # skip first few
        assets_for_feat = assets

        rows = []
        for d in dates_trade:
            feat = pd.DataFrame(
                {"score": np.random.randn(len(assets))},
                index=assets,
            )
            w = strategy.generate_weights(d, feat)
            rows.append(w)
        weights_df = pd.DataFrame(rows, index=dates_trade, columns=assets).fillna(0.0)

        config = BacktestConfig(
            rebalance_freq="W",
            initial_capital=100_000.0,
            cost_model=CostModelConfig(fixed_bps=0.0),  # no cost for clean test
            benchmark_weights={"AAPL": 0.2, "GOOG": 0.2, "MSFT": 0.2, "AMZN": 0.2, "TSLA": 0.2},
            risk_free_rate=0.0,
        )
        engine = BacktestEngine(config, weights_df, price_df)
        result = engine.run(run_id="test_bench_001")

        evaluator = BacktestEvaluator()
        all_metrics = evaluator.evaluate(result)

        assert "rel_tracking_error" in all_metrics
        assert "rel_information_ratio" in all_metrics

    def test_evaluator_summary(self, assets, dates, price_df):
        """Test evaluator summary output."""
        strategy = MomentumStrategy(n_top=2)
        dates_trade = dates[5:]

        rows = []
        for d in dates_trade:
            feat = pd.DataFrame(
                {"score": np.random.randn(len(assets))},
                index=assets,
            )
            w = strategy.generate_weights(d, feat)
            rows.append(w)
        weights_df = pd.DataFrame(rows, index=dates_trade, columns=assets).fillna(0.0)

        config = BacktestConfig(rebalance_freq="W", initial_capital=100_000.0)
        result = BacktestEngine(config, weights_df, price_df).run()

        evaluator = BacktestEvaluator()
        summary = evaluator.summary(result)

        assert "Total Return" in summary.index
        assert "Sharpe Ratio" in summary.index
        assert "Max Drawdown" in summary.index

    def test_no_nautilus_import(self):
        """
        Verify: Batch 4C backtest does NOT import NautilusTrader.

        This ensures research-layer independence from execution layer.
        """
        import core.research.backtest as bt_mod
        import core.research.strategy as strat_mod

        # Get source files
        bt_file = bt_mod.__file__
        strat_file = strat_mod.__file__

        bt_content = open(bt_file, encoding="utf-8").read()
        strat_content = open(strat_file, encoding="utf-8").read()

        # Should not mention NautilusTrader
        assert "nautilus_trader" not in bt_content.lower()
        assert "nautilus_trader" not in strat_content.lower()

        # Should not import execution layer
        assert "core.execution" not in bt_content
        assert "core.execution" not in strat_content

        # Should not have execution semantics
        forbidden = ["order_type", "limit_price", "stop_price", "time_in_force", "ExecutionIntent"]
        for kw in forbidden:
            assert kw not in bt_content, f"{kw} found in backtest module"
            assert kw not in strat_content, f"{kw} found in strategy module"

    def test_backtest_cost_impact(self, assets, dates, price_df):
        """Verify transaction costs reduce net returns."""
        strategy = MomentumStrategy(n_top=3)
        rows = []
        for d in dates:
            feat = pd.DataFrame(
                {"score": np.random.randn(len(assets))},
                index=assets,
            )
            w = strategy.generate_weights(d, feat)
            rows.append(w)
        weights_df = pd.DataFrame(rows, index=dates, columns=assets).fillna(0.0)

        # With costs
        cfg_cost = BacktestConfig(
            rebalance_freq="D",
            initial_capital=100_000.0,
            cost_model=CostModelConfig(fixed_bps=50.0),  # 50 bps = expensive
        )
        result_cost = BacktestEngine(cfg_cost, weights_df, price_df).run()

        # Without costs
        cfg_free = BacktestConfig(
            rebalance_freq="D",
            initial_capital=100_000.0,
            cost_model=CostModelConfig(fixed_bps=0.0),
        )
        result_free = BacktestEngine(cfg_free, weights_df, price_df).run()

        # Costly backtest should have lower total return
        assert result_cost.metrics["total_transaction_cost"] > 0.0
        # Net returns with costs should be <= gross returns without
        assert result_cost.metrics["total_return"] <= result_free.metrics["total_return"] + 1e-6


class TestBacktestBoundary:
    """Boundary tests: verify no execution layer leakage."""

    def test_backtest_result_no_execution_fields(self):
        """BacktestResult must not contain Order, Fill, ExecutionReport fields."""
        import inspect
        from core.research.backtest.result import BacktestResult

        src = inspect.getsource(BacktestResult)
        forbidden = ["Order", "FillRecord", "ExecutionReport", "ExecutionIntent", "Nautilus"]
        for field in forbidden:
            assert field not in src, f"{field} found in BacktestResult source"

    def test_strategy_base_no_execution_fields(self):
        """StrategyBase must not contain execution fields."""
        import inspect
        from core.research.strategy.base import StrategyBase

        src = inspect.getsource(StrategyBase)
        forbidden = ["order_type", "limit_price", "stop_price", "time_in_force", "venue"]
        for field in forbidden:
            assert field not in src, f"{field} found in StrategyBase source"

    def test_cost_model_phase1_scope(self):
        """CostModel must not have market impact / order book fields."""
        import inspect
        from core.research.backtest.cost_model import CostModel

        src = inspect.getsource(CostModel)
        forbidden = ["market_impact", "order_book", "queue", "depth", "liquidity"]
        for field in forbidden:
            assert field.lower() not in src.lower(), f"{field} found in CostModel source"
