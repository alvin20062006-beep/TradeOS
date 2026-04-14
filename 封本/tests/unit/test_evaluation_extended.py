"""
tests.unit.test_evaluation_extended
=================================
Unit tests for core.research.alpha.evaluation.metrics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.research.alpha.evaluation.metrics import FactorMetrics, FactorMetricsBundle


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def signal_factor() -> pd.Series:
    """Factor strongly correlated with labels."""
    np.random.seed(123)
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    base = np.linspace(0.5, -0.5, 100) + np.random.randn(100) * 0.1
    return pd.Series(base, index=dates)


@pytest.fixture
def forward_returns(signal_factor) -> pd.Series:
    """Forward returns correlated with the factor."""
    f = signal_factor.values
    r = f * 0.8 + np.random.randn(100) * 0.2
    return pd.Series(r, index=signal_factor.index)


# ── FactorMetrics.compute ────────────────────────────────────────────────

class TestFactorMetricsCompute:
    def test_returns_factor_metrics_instance(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns, "test_factor")
        assert isinstance(fm, FactorMetrics)
        assert fm.factor_name == "test_factor"

    def test_ic_series_in_range(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns)
        if fm.ic_series is not None:
            assert fm.ic_series.between(-1.0, 1.0).all()

    def test_ic_mean_finite(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns)
        assert isinstance(fm.ic_mean, float)
        assert not np.isnan(fm.ic_mean)

    def test_information_ratio(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns)
        # IR should be positive for a factor with consistent IC
        assert isinstance(fm.information_ratio, float)

    def test_group_ic_dict(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns, n_groups=5)
        if fm.group_ic_dict is not None:
            assert isinstance(fm.group_ic_dict, dict)
            assert len(fm.group_ic_dict) >= 1
            # Each group IC should be a Series
            for g, ic in fm.group_ic_dict.items():
                assert isinstance(ic, pd.Series)

    def test_turnover_non_negative(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns)
        if fm.turnover_series is not None:
            # diff() creates NaN at position 0; drop before asserting
            assert (fm.turnover_series.dropna() >= 0.0).all()

    def test_turnover_range(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns)
        if fm.turnover_series is not None:
            assert fm.turnover_series.max() <= 2.0  # Theoretical max ≈ 2

    def test_insufficient_data_returns_defaults(self):
        short_factor = pd.Series([1.0, 2.0])
        short_labels = pd.Series([0.1, 0.2])
        fm = FactorMetrics.compute(short_factor, short_labels, "short")
        assert fm.ic_series is None
        assert fm.ic_mean == 0.0

    def test_ic_series_alignment_with_labels(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns)
        if fm.ic_series is not None:
            assert len(fm.ic_series) <= len(signal_factor)


# ── FactorMetricsBundle ──────────────────────────────────────────────────

class TestFactorMetricsBundle:
    def test_add_updates_bundle(self):
        bundle = FactorMetricsBundle()
        fm1 = FactorMetrics(factor_name="F1", ic_mean=0.05, ic_std=0.02, information_ratio=2.5)
        bundle.add(fm1)
        assert "F1" in bundle.factor_metrics
        assert bundle.best_factor == "F1"

    def test_best_factor_by_ir(self):
        bundle = FactorMetricsBundle()
        bundle.add(FactorMetrics(factor_name="F1", ic_mean=0.03, ic_std=0.03, information_ratio=1.0))
        bundle.add(FactorMetrics(factor_name="F2", ic_mean=0.05, ic_std=0.01, information_ratio=5.0))
        bundle.add(FactorMetrics(factor_name="F3", ic_mean=0.01, ic_std=0.02, information_ratio=0.5))
        assert bundle.best_factor == "F2"

    def test_ic_summary_columns(self):
        bundle = FactorMetricsBundle()
        bundle.add(FactorMetrics(factor_name="F1", ic_mean=0.05, ic_std=0.02, information_ratio=2.5))
        summary = bundle.ic_summary()
        assert isinstance(summary, pd.DataFrame)
        assert "ic_mean" in summary.columns
        assert "ic_std" in summary.columns
        assert "information_ratio" in summary.columns
        assert "F1" in summary.index

    def test_top_factors(self):
        bundle = FactorMetricsBundle()
        for i in range(8):
            bundle.add(
                FactorMetrics(
                    factor_name=f"F{i}",
                    ic_mean=0.01 * i,
                    ic_std=0.02,
                    information_ratio=0.5 * i,
                )
            )
        top = bundle.top_factors(n=3)
        assert len(top) <= 3
        assert isinstance(top, list)

    def test_top_factors_empty_bundle(self):
        bundle = FactorMetricsBundle()
        top = bundle.top_factors()
        assert top == []

    def test_as_dict(self, signal_factor, forward_returns):
        fm = FactorMetrics.compute(signal_factor, forward_returns, "dict_test")
        d = fm.as_dict()
        assert isinstance(d, dict)
        assert d["factor_name"] == "dict_test"
        assert "ic_mean" in d
        assert "information_ratio" in d
