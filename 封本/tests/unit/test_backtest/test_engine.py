"""
test_engine.py
=============
Unit tests for BacktestEngine.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from core.research.backtest.engine import BacktestEngine, BacktestDataError
from core.research.backtest.schema import BacktestConfig
from core.research.backtest.cost_model import CostModel


class TestBacktestEngine:
    @pytest.fixture
    def synthetic_data(self):
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        weights = pd.DataFrame(
            {"A": [0.5, 0.5, 0.5, 0.5, 0.5], "B": [0.5, 0.5, 0.5, 0.5, 0.5]},
            index=dates,
        )
        prices = pd.DataFrame(
            {
                "A": [100.0, 101.0, 102.01, 103.0301, 104.060401],
                "B": [100.0, 100.5, 101.0025, 101.5075, 102.015],
            },
            index=dates,
        )
        return weights, prices

    def test_engine_runs(self, synthetic_data):
        weights, prices = synthetic_data
        config = BacktestConfig(initial_capital=1_000_000.0)
        engine = BacktestEngine(weights_series=weights, prices=prices, config=config)
        result = engine.run()
        assert not result.returns_series.empty
        assert result.metrics.get("total_return", 0) > 0

    def test_empty_weights_rejected(self):
        empty_weights = pd.DataFrame(columns=["A", "B"])
        prices = pd.DataFrame({"A": [100.0], "B": [100.0]}, index=pd.date_range("2024-01-01", periods=1))
        config = BacktestConfig()
        with pytest.raises(BacktestDataError):
            BacktestEngine(empty_weights, prices, config)

    def test_mismatched_columns_rejected(self, synthetic_data):
        weights, prices = synthetic_data
        prices["C"] = [100.0] * len(prices)
        config = BacktestConfig()
        with pytest.raises(BacktestDataError):
            BacktestEngine(weights, prices, config)

    def test_cost_model_applied(self, synthetic_data):
        weights, prices = synthetic_data
        config = BacktestConfig(initial_capital=1_000_000.0)
        from core.research.backtest.schema import CostModelConfig
        cm = CostModel(CostModelConfig(fixed_bps=10.0))
        engine = BacktestEngine(weights_series=weights, prices=prices, config=config, cost_model=cm)
        result = engine.run()
        assert "total_cost" in result.metrics

    def test_no_execution_fields(self, synthetic_data):
        weights, prices = synthetic_data
        config = BacktestConfig()
        engine = BacktestEngine(weights_series=weights, prices=prices, config=config)
        result = engine.run()
        d = result.to_dict()
        forbidden = ["order_id", "fill_price", "order_type", "limit_price", "time_in_force"]
        for f in forbidden:
            assert f not in d
