"""
test_cost_model.py
==================
Unit tests for CostModel.
"""

import pytest
import pandas as pd

from core.research.backtest.cost_model import CostModel
from core.research.backtest.schema import CostModelConfig


class TestCostModel:
    def test_default_fixed_bps(self):
        model = CostModel()
        assert model.config.fixed_bps == 5.0
        assert model.cost_for_trade(10_000.0) == 5.0

    def test_with_slippage(self):
        cfg = CostModelConfig(fixed_bps=5.0, slippage_bps=2.0)
        model = CostModel(cfg)
        assert model.cost_for_trade(10_000.0) == 7.0

    def test_min_cost_applied(self):
        cfg = CostModelConfig(fixed_bps=1.0, slippage_bps=0.0, min_cost=10.0)
        model = CostModel(cfg)
        assert model.cost_for_trade(1_000.0) == 10.0

    def test_cost_for_trade_zero(self):
        model = CostModel()
        assert model.cost_for_trade(0.0) == 0.0

    def test_turnover_rate_equal_weights(self):
        model = CostModel()
        prev = pd.Series([0.5, 0.5], index=["AAPL", "GOOG"])
        new = pd.Series([0.5, 0.5], index=["AAPL", "GOOG"])
        assert model.turnover_rate(prev, new) == 0.0

    def test_turnover_rate_full_rebalance(self):
        model = CostModel()
        prev = pd.Series([1.0, 0.0], index=["AAPL", "GOOG"])
        new = pd.Series([0.0, 1.0], index=["AAPL", "GOOG"])
        assert model.turnover_rate(prev, new) == 1.0

    def test_turnover_rate_partial(self):
        model = CostModel()
        prev = pd.Series([0.6, 0.4], index=["AAPL", "GOOG"])
        new = pd.Series([0.5, 0.5], index=["AAPL", "GOOG"])
        assert abs(model.turnover_rate(prev, new) - 0.1) < 1e-9

    def test_costs_for_period(self):
        cfg = CostModelConfig(fixed_bps=10.0, slippage_bps=0.0)
        model = CostModel(cfg)
        prev = pd.Series([0.0, 0.0], index=["AAPL", "GOOG"])
        new = pd.Series([0.6, 0.4], index=["AAPL", "GOOG"])
        prices = pd.Series([100.0, 200.0], index=["AAPL", "GOOG"])
        total, per_asset = model.costs_for_period(prev, new, prices, 100_000.0)
        assert total == 100.0
        assert per_asset["AAPL"] == 60.0
        assert per_asset["GOOG"] == 40.0

    def test_no_trade_cost_zero(self):
        cfg = CostModelConfig(fixed_bps=10.0, min_cost=1.0)
        model = CostModel(cfg)
        prev = pd.Series([0.5, 0.5], index=["AAPL", "GOOG"])
        new = pd.Series([0.5, 0.5], index=["AAPL", "GOOG"])
        prices = pd.Series([100.0, 200.0], index=["AAPL", "GOOG"])
        total, per_asset = model.costs_for_period(prev, new, prices, 100_000.0)
        assert total == 0.0
