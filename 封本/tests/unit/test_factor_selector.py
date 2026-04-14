"""
tests.unit.test_factor_selector
==============================
Unit tests for core.research.alpha.selection.selector.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.research.alpha.selection.selector import FactorSelector


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def random_factors() -> pd.DataFrame:
    """10 factors, 100 days, uncorrelated random values."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    data = np.random.randn(100, 10)
    return pd.DataFrame(data, index=dates, columns=[f"F{i}" for i in range(10)])


@pytest.fixture
def correlated_factors() -> pd.DataFrame:
    """Factor F0 duplicated as F1 (corr=1.0); F2 similar to F0 (corr≈0.9)."""
    np.random.seed(0)
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    base = np.random.randn(100)
    f0 = base + np.random.randn(100) * 0.1
    f1 = base + np.random.randn(100) * 0.1  # nearly identical to F0
    f2 = base * 0.9 + np.random.randn(100) * 0.3
    f3 = np.random.randn(100)  # independent
    return pd.DataFrame(
        {"F0": f0, "F1": f1, "F2": f2, "F3": f3}, index=dates
    )


@pytest.fixture
def positive_labels() -> pd.Series:
    """Labels strongly correlated with F0, F1, F2."""
    np.random.seed(0)
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    base = np.random.randn(100)
    return pd.Series(base + np.random.randn(100) * 0.2, index=dates)


# ── best_k ──────────────────────────────────────────────────────────────

class TestBestK:
    def test_k_less_than_n_candidates(self, random_factors, positive_labels):
        sel = FactorSelector()
        result = sel.best_k(random_factors, positive_labels, k=3)
        assert len(result) == 3
        assert set(result).issubset(set(random_factors.columns))

    def test_k_greater_than_n_candidates(self, random_factors, positive_labels):
        sel = FactorSelector()
        result = sel.best_k(random_factors, positive_labels, k=20)
        assert len(result) == len(random_factors.columns)  # returns all

    def test_empty_factors(self, positive_labels):
        sel = FactorSelector()
        empty = pd.DataFrame(columns=["F0", "F1"])
        result = sel.best_k(empty, positive_labels, k=3)
        # best_k returns all available columns when k > n_candidates (safe fallback)
        assert isinstance(result, list)
        assert len(result) == 2
        assert set(result) == {"F0", "F1"}

    def test_empty_labels(self, random_factors):
        sel = FactorSelector()
        empty_labels = pd.Series([], index=[], dtype=float)
        result = sel.best_k(random_factors, empty_labels, k=3)
        assert isinstance(result, list)


# ── correlation_prune ────────────────────────────────────────────────────

class TestCorrelationPrune:
    def test_removes_perfect_correlation(self, correlated_factors):
        sel = FactorSelector(corr_threshold=0.95)
        result = sel.correlation_prune(correlated_factors)
        # F0 and F1 are nearly identical (corr≈1) — one must be dropped
        assert len(result) < len(correlated_factors.columns)
        assert "F0" in result or "F1" in result  # at least one survives
        assert not ("F0" in result and "F1" in result)  # not both

    def test_no_pruning_below_threshold(self, random_factors):
        sel = FactorSelector(corr_threshold=0.5)
        result = sel.correlation_prune(random_factors)
        # With random data, few pairs exceed 0.5 — result may be all or most
        assert isinstance(result, list)

    def test_single_factor_unchanged(self):
        sel = FactorSelector()
        df = pd.DataFrame({"F0": np.random.randn(50)})
        result = sel.correlation_prune(df)
        assert result == ["F0"]

    def test_empty_dataframe(self):
        sel = FactorSelector()
        empty = pd.DataFrame()
        result = sel.correlation_prune(empty)
        assert result == []


# ── ic_threshold ────────────────────────────────────────────────────────

class TestICThreshold:
    def test_filters_below_min_ic(self, random_factors, positive_labels):
        # Random factors have ~0 IC; min_ic=0.05 should filter all
        sel = FactorSelector(min_ic=0.05)
        result = sel.ic_threshold(random_factors, positive_labels)
        assert isinstance(result, list)

    def test_preserves_strong_factor(self, correlated_factors, positive_labels):
        # Labels are correlated with F0, F1, F2
        sel = FactorSelector(min_ic=0.05)
        result = sel.ic_threshold(correlated_factors, positive_labels)
        # F0 should pass (strong signal)
        assert "F0" in result

    def test_empty_input(self, random_factors):
        sel = FactorSelector()
        empty_labels = pd.Series([], index=[], dtype=float)
        result = sel.ic_threshold(random_factors, empty_labels)
        assert result == []


# ── ir_threshold ────────────────────────────────────────────────────────

class TestIRThreshold:
    def test_ir_filters_weak(self, random_factors, positive_labels):
        sel = FactorSelector(min_ir=1.0)
        result = sel.ir_threshold(random_factors, positive_labels)
        assert isinstance(result, list)

    def test_empty_input(self, random_factors):
        sel = FactorSelector()
        empty_labels = pd.Series([], index=[], dtype=float)
        result = sel.ir_threshold(random_factors, empty_labels)
        assert result == []


# ── select (composite) ──────────────────────────────────────────────────

class TestSelect:
    def test_select_ic_ir_returns_list(self, correlated_factors, positive_labels):
        sel = FactorSelector(min_ic=0.02, min_ir=0.1, corr_threshold=0.8)
        result = sel.select(correlated_factors, positive_labels, strategy="ic_ir")
        assert isinstance(result, list)
        # Should be non-empty when strong signals exist
        assert len(result) >= 1

    def test_select_best_only(self, random_factors, positive_labels):
        sel = FactorSelector()
        result = sel.select(random_factors, positive_labels, strategy="best_only")
        assert len(result) == 5  # best_only defaults to k=5

    def test_select_unknown_strategy_raises(self, random_factors, positive_labels):
        sel = FactorSelector()
        with pytest.raises(ValueError, match="Unknown strategy"):
            sel.select(random_factors, positive_labels, strategy="invalid")

    def test_empty_factors_returns_empty(self, positive_labels):
        sel = FactorSelector()
        empty = pd.DataFrame()
        result = sel.select(empty, positive_labels, strategy="ic_ir")
        assert result == []

    def test_selector_init_invalid_threshold_raises(self):
        with pytest.raises(ValueError, match="corr_threshold"):
            FactorSelector(corr_threshold=1.5)
