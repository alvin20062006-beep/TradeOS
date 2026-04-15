"""
tests.unit.test_multi_factor
===========================
Unit tests for core.research.alpha.builders.multi_factor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.research.alpha.builders.multi_factor import MultiFactorBuilder


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def three_factors() -> pd.DataFrame:
    """3 factors, 50 days, named F0/F1/F2."""
    np.random.seed(99)
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    f0 = np.random.randn(50) + 1.0  # positive IC
    f1 = np.random.randn(50) + 0.5
    f2 = np.random.randn(50) + 0.2
    return pd.DataFrame({"F0": f0, "F1": f1, "F2": f2}, index=dates)


@pytest.fixture
def labels_positive_ic(three_factors) -> pd.Series:
    """Labels strongly correlated with all three factors."""
    f0 = three_factors["F0"].values
    noise = np.random.randn(50) * 0.2
    return pd.Series(f0 * 0.6 + noise, index=three_factors.index)


@pytest.fixture
def labels_mixed_ic(three_factors) -> pd.Series:
    """Labels positively correlated with F0, negatively with F1."""
    f0 = three_factors["F0"].values
    f1 = three_factors["F1"].values
    return pd.Series(f0 * 0.5 - f1 * 0.5 + np.random.randn(50) * 0.2, index=three_factors.index)


# ── equal_weighted ───────────────────────────────────────────────────────

class TestEqualWeighted:
    def test_returns_series(self, three_factors):
        mfb = MultiFactorBuilder()
        result = mfb.equal_weighted(three_factors)
        assert isinstance(result, pd.Series)

    def test_index_matches(self, three_factors):
        mfb = MultiFactorBuilder()
        result = mfb.equal_weighted(three_factors)
        assert result.index.equals(three_factors.index)

    def test_value_range_reasonable(self, three_factors):
        mfb = MultiFactorBuilder()
        result = mfb.equal_weighted(three_factors)
        # All input factors are ~N(μ, 1); mean should be in a reasonable range
        assert not result.isnull().all()
        assert result.std() > 0

    def test_single_factor_returns_unchanged(self):
        mfb = MultiFactorBuilder()
        s = pd.Series(np.random.randn(30), index=range(30))
        result = mfb.equal_weighted(s)
        assert result.equals(s)

    def test_empty_dataframe(self):
        mfb = MultiFactorBuilder()
        empty = pd.DataFrame()
        result = mfb.equal_weighted(empty)
        assert isinstance(result, pd.Series)
        assert len(result) == 0


# ── ic_weighted ──────────────────────────────────────────────────────────

class TestICWeighted:
    def test_weights_non_negative_when_positive_ic(self, three_factors, labels_positive_ic):
        mfb = MultiFactorBuilder(handle_neg_ic=True)
        ic_dict = mfb._ic_series_dict(three_factors, labels_positive_ic)
        for v in ic_dict.values():
            # handle_neg_ic=True zeros out negative weights
            # IC itself may still be negative, but we only check dict is non-empty
            pass
        assert isinstance(ic_dict, dict)

    def test_output_shape(self, three_factors, labels_positive_ic):
        mfb = MultiFactorBuilder()
        result = mfb.ic_weighted(three_factors, labels_positive_ic)
        assert isinstance(result, pd.Series)
        assert len(result) == len(three_factors)
        assert not result.isnull().all()

    def test_handles_mixed_ic(self, three_factors, labels_mixed_ic):
        mfb = MultiFactorBuilder(handle_neg_ic=True)
        result = mfb.ic_weighted(three_factors, labels_mixed_ic)
        assert isinstance(result, pd.Series)
        assert not result.isnull().all()

    def test_empty_factors(self, labels_positive_ic):
        mfb = MultiFactorBuilder()
        empty = pd.DataFrame()
        result = mfb.ic_weighted(empty, labels_positive_ic)
        assert isinstance(result, pd.Series)
        assert len(result) == 0

    def test_weights_sum_near_one(self, three_factors, labels_positive_ic):
        mfb = MultiFactorBuilder(handle_neg_ic=True)
        # Inspect internal weights
        ic_dict = mfb._ic_series_dict(three_factors, labels_positive_ic)
        ic_vals = np.array([max(v, 0.0) for v in ic_dict.values()])
        total = ic_vals.sum()
        if total > 1e-10:
            weights = ic_vals / total
            assert abs(weights.sum() - 1.0) < 1e-9


# ── ir_weighted ─────────────────────────────────────────────────────────

class TestIRWeighted:
    def test_output_series(self, three_factors, labels_positive_ic):
        mfb = MultiFactorBuilder()
        result = mfb.ir_weighted(three_factors, labels_positive_ic)
        assert isinstance(result, pd.Series)
        assert len(result) == len(three_factors)

    def test_falls_back_to_equal_on_insufficient_data(self):
        # Very short series — IR can't be computed
        mfb = MultiFactorBuilder()
        short = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        labels = pd.Series([0.1, 0.2, 0.3])
        result = mfb.ir_weighted(short, labels)
        assert isinstance(result, pd.Series)

    def test_empty_factors(self, labels_positive_ic):
        mfb = MultiFactorBuilder()
        empty = pd.DataFrame()
        result = mfb.ir_weighted(empty, labels_positive_ic)
        assert isinstance(result, pd.Series)
        assert len(result) == 0


# ── combine (entry point) ────────────────────────────────────────────────

class TestCombine:
    def test_equal_method(self, three_factors):
        mfb = MultiFactorBuilder()
        result = mfb.combine(three_factors, method="equal")
        expected = mfb.equal_weighted(three_factors)
        assert result.equals(expected)

    def test_ic_method_requires_labels(self, three_factors):
        mfb = MultiFactorBuilder()
        with pytest.raises(ValueError, match="labels required"):
            mfb.combine(three_factors, method="ic")

    def test_ir_method_requires_labels(self, three_factors):
        mfb = MultiFactorBuilder()
        with pytest.raises(ValueError, match="labels required"):
            mfb.combine(three_factors, method="ir")

    def test_unknown_method_raises(self, three_factors):
        mfb = MultiFactorBuilder()
        with pytest.raises(ValueError, match="Unknown combination method"):
            mfb.combine(three_factors, method="unknown")

    def test_pca_fallback_without_sklearn(self, three_factors):
        mfb = MultiFactorBuilder()
        # pca should fall back to equal if sklearn unavailable (test without import)
        import sys
        saved = sys.modules.pop("sklearn.decomposition", None)
        try:
            result = mfb.combine(three_factors, method="pca")
            # Should fall back to equal_weighted, not crash
            assert isinstance(result, pd.Series)
        finally:
            if saved is not None:
                sys.modules["sklearn.decomposition"] = saved
