"""
test_backtest_integration.py
===========================
Integration test: BacktestEngine end-to-end with StrategyBase.

Tests the full pipeline:
Strategy → weights → BacktestEngine → BacktestResult
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from core.research.strategy.base import MomentumStrategy, EqualWeightStrategy
from core.research.strategy.signal import StrategySignal, StrategyIntent, SignalDirection
from core.research.backtest.engine import BacktestEngine
from core.research.backtest.schema import BacktestConfig, CostModelConfig
from core.research.backtest.cost_model import CostModel
from core.research.backtest.result import BacktestResult


class TestStrategyToBacktest:
    """End-to-end: Strategy → weights → BacktestEngine → BacktestResult."""

    @pytest.fixture
    def price_data(self):
        """20-day price data for 3 assets."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=20, freq="B")
        # Asset A: upward trend, B: flat, C: downward trend
        prices_a = 100.0 * np.cumprod(1 + np.random.randn(20) * 0.01 + 0.002)
        prices_b = 100.0 * np.cumprod(1 + np.random.randn(20) * 0.005)
        prices_c = 100.0 * np.cumprod(1 + np.random.randn(20) * 0.01 - 0.002)
        return pd.DataFrame(
            {"A": prices_a, "B": prices_b, "C": prices_c},
            index=dates,
        )

    def test_equal_weight_strategy_backtest(self, price_data):
        """EqualWeightStrategy → weights → BacktestEngine → positive result."""
        strat = EqualWeightStrategy()
        dates = price_data.index
        n = len(dates)

        # Generate weights for each date
        weights_records = []
        features_by_date = {}
        for dt in dates:
            feat = pd.DataFrame(
                {"price": price_data.loc[dt].values},
                index=["A", "B", "C"],
            )
            w = strat.generate_weights(dt, feat)
            weights_records.append(w)
            features_by_date[dt] = feat

        weights_df = pd.DataFrame(weights_records, index=dates)

        config = BacktestConfig(initial_capital=1_000_000.0)
        engine = BacktestEngine(
            weights_series=weights_df,
            prices=price_data,
            config=config,
        )
        result = engine.run()

        assert isinstance(result, BacktestResult)
        assert not result.returns_series.empty
        assert "total_return" in result.metrics
        assert "sharpe_ratio" in result.metrics

    def test_momentum_strategy_with_costs(self, price_data):
        """MomentumStrategy + cost model → BacktestResult with costs."""
        strat = MomentumStrategy(long_only=True)
        dates = price_data.index

        weights_records = []
        for dt in dates:
            # Use price level as momentum proxy
            feat = pd.DataFrame(
                {"momentum": price_data.loc[dt].values},
                index=["A", "B", "C"],
            )
            w = strat.generate_weights(dt, feat)
            weights_records.append(w)

        weights_df = pd.DataFrame(weights_records, index=dates)

        cost_model = CostModel(CostModelConfig(fixed_bps=5.0, slippage_bps=1.0))
        config = BacktestConfig(initial_capital=1_000_000.0, risk_free_rate=0.02)
        engine = BacktestEngine(
            weights_series=weights_df,
            prices=price_data,
            config=config,
            cost_model=cost_model,
        )
        result = engine.run()

        assert result.metrics["total_cost"] > 0
        assert result.metrics["total_return"] != 0.0

    def test_signals_to_intent_to_backtest(self, price_data):
        """StrategySignal → StrategyIntent → BacktestEngine."""
        # Generate signals
        signals = [
            StrategySignal(
                asset_id="A",
                timestamp=price_data.index[0],
                direction=SignalDirection.LONG,
                confidence=0.8,
            ),
            StrategySignal(
                asset_id="B",
                timestamp=price_data.index[0],
                direction=SignalDirection.LONG,
                confidence=0.5,
            ),
            StrategySignal(
                asset_id="C",
                timestamp=price_data.index[0],
                direction=SignalDirection.NEUTRAL,
                confidence=0.1,
            ),
        ]

        strat = EqualWeightStrategy()
        intent = strat.signals_to_intent(signals, price_data.index[0])

        # Build weights series from intent
        weights_df = pd.DataFrame(
            [intent.to_weights_series()] * len(price_data),
            index=price_data.index,
        )

        config = BacktestConfig(initial_capital=500_000.0)
        engine = BacktestEngine(
            weights_series=weights_df,
            prices=price_data,
            config=config,
        )
        result = engine.run()

        assert not result.returns_series.empty
        assert isinstance(result.metrics, dict)

    def test_from_alpha_signal_to_backtest(self, price_data):
        """StrategySignal.from_alpha → weights → BacktestEngine."""
        # Use first-date returns as alpha
        alpha = price_data.iloc[0] / price_data.iloc[0].shift(1).fillna(100) - 1
        sig = StrategySignal.from_alpha(alpha, strategy_id="alpha_test")
        weights = sig.to_weights()

        weights_df = pd.DataFrame(
            [weights] * len(price_data),
            index=price_data.index,
        )
        # Align columns
        for col in price_data.columns:
            if col not in weights_df.columns:
                weights_df[col] = 0.0
        weights_df = weights_df[price_data.columns]

        config = BacktestConfig(initial_capital=1_000_000.0)
        engine = BacktestEngine(
            weights_series=weights_df,
            prices=price_data,
            config=config,
        )
        result = engine.run()
        assert not result.returns_series.empty

    def test_no_execution_fields_in_result(self, price_data):
        """Verify no execution semantics leak into BacktestResult."""
        strat = EqualWeightStrategy()
        dates = price_data.index
        weights_records = []
        for dt in dates:
            feat = pd.DataFrame({"price": price_data.loc[dt].values}, index=["A", "B", "C"])
            w = strat.generate_weights(dt, feat)
            weights_records.append(w)

        weights_df = pd.DataFrame(weights_records, index=dates)
        config = BacktestConfig(initial_capital=1_000_000.0)
        engine = BacktestEngine(weights_series=weights_df, prices=price_data, config=config)
        result = engine.run()

        d = result.to_dict()
        forbidden = [
            "order_id", "fill_price", "order_type", "limit_price",
            "time_in_force", "execution_report", "fill",
        ]
        for f in forbidden:
            assert f not in d, f"Forbidden execution field '{f}' found in BacktestResult.to_dict()"

    def test_boundary_no_nautilus_dependency(self):
        """Verify backtest modules have no NautilusTrader imports."""
        import importlib
        modules = [
            "core.research.backtest.result",
            "core.research.backtest.cost_model",
            "core.research.backtest.engine",
            "core.research.backtest.schema",
            "core.research.strategy.signal",
            "core.research.strategy.base",
        ]
        for mod_name in modules:
            mod = importlib.import_module(mod_name)
            source = open(mod.__file__, "r", encoding="utf-8").read()
            assert "nautilus" not in source.lower(), f"{mod_name} imports nautilus"
