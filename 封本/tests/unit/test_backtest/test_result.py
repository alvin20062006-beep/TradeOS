"""
test_result.py
=============
Unit tests for BacktestResult.
"""

import pytest
import pandas as pd
import numpy as np

from core.research.backtest.result import BacktestResult


class TestBacktestResultFromSeries:
    def test_from_series_basic(self):
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        returns = pd.Series([0.01, -0.005, 0.02, 0.01, -0.01], index=dates)
        gross = returns.copy()
        net = returns.copy()
        positions = pd.DataFrame(
            [[0.6, 0.4]] * 5,
            index=dates,
            columns=["AAPL", "GOOG"],
        )
        turnover = pd.Series([0.1] * 5, index=dates)
        costs = pd.Series([10.0] * 5, index=dates)
        cfg = {"risk_free_rate": 0.04}

        result = BacktestResult.from_series(
            returns=returns,
            gross=gross,
            net=net,
            positions=positions,
            turnover=turnover,
            costs=costs,
            config_dict=cfg,
        )

        assert len(result.returns_series) == 5
        assert len(result.equity_curve) == 5
        assert "total_return" in result.metrics
        assert "sharpe_ratio" in result.metrics
        assert "run_id" in result.metadata
        assert result.metadata["n_rebalance_periods"] == 5

    def test_metrics_computed(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        returns = pd.Series([0.01] * 10, index=dates)
        gross = returns.copy()
        net = returns.copy()
        positions = pd.DataFrame(
            [[0.5, 0.5]] * 10,
            index=dates,
            columns=["AAPL", "GOOG"],
        )
        turnover = pd.Series([0.0] * 10, index=dates)
        costs = pd.Series([0.0] * 10, index=dates)

        result = BacktestResult.from_series(
            returns, gross, net, positions, turnover, costs, {}
        )
        assert result.metrics["total_return"] > 0.0
        assert result.metrics["win_rate"] == 1.0

    def test_to_dict_serializable(self):
        dates = pd.date_range("2024-01-01", periods=3, freq="D")
        returns = pd.Series([0.01, -0.005, 0.02], index=dates)
        gross = returns.copy()
        net = returns.copy()
        positions = pd.DataFrame(
            [[0.6, 0.4], [0.5, 0.5], [0.7, 0.3]],
            index=dates,
            columns=["AAPL", "GOOG"],
        )
        turnover = pd.Series([0.1, 0.05, 0.15], index=dates)
        costs = pd.Series([5.0, 2.5, 7.5], index=dates)

        result = BacktestResult.from_series(
            returns, gross, net, positions, turnover, costs, {"risk_free_rate": 0.0}
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "metrics" in d
        assert "metadata" in d

    def test_empty_series(self):
        dates = pd.DatetimeIndex([])
        returns = pd.Series([], dtype=float, index=dates)
        result = BacktestResult.from_series(
            returns, returns, returns,
            pd.DataFrame(index=dates),
            returns, returns, {},
        )
        assert result.metrics["total_return"] == 0.0
        assert result.metrics["sharpe_ratio"] == 0.0
