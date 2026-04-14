"""
tests/unit/test_backtest_schema.py
==================================
Unit tests for backtest schema (BacktestConfig, CostModelConfig).
"""

import pytest
from pathlib import Path

from core.research.backtest.schema import BacktestConfig, CostModelConfig


class TestCostModelConfig:
    def test_defaults(self):
        cfg = CostModelConfig()
        assert cfg.fixed_bps == 5.0
        assert cfg.slippage_bps == 0.0
        assert cfg.min_cost == 0.0

    def test_total_cost_bps(self):
        cfg = CostModelConfig(fixed_bps=10.0, slippage_bps=2.0)
        assert cfg.total_cost_bps(10000.0) == 12.0  # 10 + 2

    def test_total_cost_absolute(self):
        cfg = CostModelConfig(fixed_bps=10.0, slippage_bps=0.0, min_cost=0.0)
        cost = cfg.total_cost_absolute(10000.0)
        assert cost == 10.0  # 10 bps * $10,000 / 10000 = $10.00

    def test_min_cost_enforced(self):
        cfg = CostModelConfig(fixed_bps=1.0, slippage_bps=0.0, min_cost=5.0)
        cost = cfg.total_cost_absolute(1000.0)
        # 1 bps * $1000 / 10000 = $0.10, but min_cost = $5.00
        assert cost == 5.0

    def test_negative_rejected(self):
        with pytest.raises(Exception):  # pydantic validation error
            CostModelConfig(fixed_bps=-1.0)


class TestBacktestConfig:
    def test_defaults(self):
        cfg = BacktestConfig()
        assert cfg.rebalance_freq == "W"
        assert cfg.initial_capital == 1_000_000.0
        assert cfg.cost_model.fixed_bps == 5.0
        assert cfg.risk_free_rate == 0.0

    def test_full_config(self):
        cfg = BacktestConfig(
            rebalance_freq="ME",
            initial_capital=500_000.0,
            cost_model=CostModelConfig(fixed_bps=3.0, slippage_bps=1.0),
            risk_free_rate=0.04,
            benchmark_weights={"AAPL": 0.6, "GOOG": 0.4},
        )
        assert cfg.rebalance_freq == "ME"
        assert cfg.initial_capital == 500_000.0
        assert cfg.cost_model.fixed_bps == 3.0
        assert cfg.risk_free_rate == 0.04
        assert cfg.benchmark_weights == {"AAPL": 0.6, "GOOG": 0.4}

    def test_benchmark_must_sum_to_one(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            BacktestConfig(benchmark_weights={"AAPL": 0.3, "GOOG": 0.4})

    def test_output_dir_created(self, tmp_path):
        out_dir = tmp_path / "reports"
        cfg = BacktestConfig(output_dir=out_dir)
        cfg.create_output_dir()
        assert out_dir.exists()
        assert out_dir.is_dir()
