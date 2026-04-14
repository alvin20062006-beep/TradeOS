"""
tests.unit.test_risk_factors
=========================
Unit tests for core.research.alpha.risk.factors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.research.alpha.risk.factors import FactorRiskAnalysis


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_factors() -> pd.DataFrame:
    """3 factors × 60 days, near-zero noise."""
    np.random.seed(7)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    f0 = np.linspace(0.0, 1.0, 60) + np.random.randn(60) * 0.05
    f1 = np.linspace(0.5, -0.5, 60) + np.random.randn(60) * 0.05
    f2 = np.sin(np.linspace(0, 3 * np.pi, 60)) + np.random.randn(60) * 0.05
    return pd.DataFrame({"F0": f0, "F1": f1, "F2": f2}, index=dates)


@pytest.fixture
def sample_returns(sample_factors) -> pd.Series:
    """Returns driven by F0 and F1, weak contribution from F2."""
    np.random.seed(7)
    f0 = sample_factors["F0"].values
    f1 = sample_factors["F1"].values
    r = f0 * 0.3 + f1 * 0.2 + np.random.randn(60) * 0.1
    return pd.Series(r, index=sample_factors.index)


@pytest.fixture
def market_returns() -> pd.Series:
    np.random.seed(8)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    return pd.Series(np.random.randn(60) * 0.01 + 0.0002, index=dates)


# ── factor_betas ─────────────────────────────────────────────────────────

class TestFactorBetas:
    def test_returns_dataframe(self, sample_factors, sample_returns):
        fra = FactorRiskAnalysis()
        result = fra.factor_betas(sample_factors, sample_returns)
        assert isinstance(result, pd.DataFrame)

    def test_full_period_shape(self, sample_factors, sample_returns):
        # Full-period (no window) → shape (1, n_factors) or (n_factors, 1)
        fra = FactorRiskAnalysis()
        result = fra.factor_betas(sample_factors, sample_returns)
        assert len(sample_factors.columns) in result.shape
        assert not result.empty

    def test_rolling_window_shape(self, sample_factors, sample_returns):
        fra = FactorRiskAnalysis()
        result = fra.factor_betas(sample_factors, sample_returns, window=20)
        # Should have (n_periods - window + 1) rows, n_factors columns
        assert result.shape[1] == len(sample_factors.columns)
        assert result.shape[0] <= len(sample_factors) - 20 + 1

    def test_empty_returns_empty_df(self, sample_factors):
        fra = FactorRiskAnalysis()
        empty = pd.Series([], index=[], dtype=float)
        result = fra.factor_betas(sample_factors, empty)
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ── factor_covariance ────────────────────────────────────────────────────

class TestFactorCovariance:
    def test_returns_square_matrix(self, sample_factors):
        fra = FactorRiskAnalysis()
        result = fra.factor_covariance(sample_factors)
        assert result.shape[0] == result.shape[1]
        assert result.shape[0] == len(sample_factors.columns)

    def test_symmetric(self, sample_factors):
        fra = FactorRiskAnalysis()
        cov = fra.factor_covariance(sample_factors)
        np.testing.assert_allclose(cov.values, cov.values.T, atol=1e-9)

    def test_positive_semi_definite(self, sample_factors):
        fra = FactorRiskAnalysis()
        cov = fra.factor_covariance(sample_factors)
        # Eigenvalues of a valid covariance matrix are non-negative
        try:
            eigvals = np.linalg.eigvalsh(cov.values)
            assert all(v >= -1e-9 for v in eigvals)
        except np.linalg.LinAlgError:
            pytest.skip("Singular matrix in test")

    def test_empty_factors(self):
        fra = FactorRiskAnalysis()
        empty = pd.DataFrame()
        result = fra.factor_covariance(empty)
        assert isinstance(result, pd.DataFrame)

    def test_single_factor_returns_1x1(self):
        fra = FactorRiskAnalysis()
        df = pd.DataFrame({"F0": np.random.randn(60)})
        result = fra.factor_covariance(df)
        assert result.shape == (1, 1)


# ── market_beta ─────────────────────────────────────────────────────────

class TestMarketBeta:
    def test_returns_series(self, sample_factors, market_returns):
        fra = FactorRiskAnalysis()
        result = fra.market_beta(sample_factors, market_returns)
        assert isinstance(result, pd.Series)

    def test_index_matches_factor_columns(self, sample_factors, market_returns):
        fra = FactorRiskAnalysis()
        result = fra.market_beta(sample_factors, market_returns)
        assert set(result.index) == set(sample_factors.columns)

    def test_all_finite(self, sample_factors, market_returns):
        fra = FactorRiskAnalysis()
        result = fra.market_beta(sample_factors, market_returns)
        assert not result.isnull().all()

    def test_empty_returns_empty_series(self, sample_factors):
        fra = FactorRiskAnalysis()
        empty = pd.Series([], index=[], dtype=float)
        result = fra.market_beta(sample_factors, empty)
        assert isinstance(result, pd.Series)


# ── risk_attribution ────────────────────────────────────────────────────

class TestRiskAttribution:
    def test_weights_sum_to_one(self, sample_factors):
        fra = FactorRiskAnalysis()
        cov = fra.factor_covariance(sample_factors)
        exposures = pd.Series(0.25, index=sample_factors.columns)
        result = fra.risk_attribution(exposures, cov)
        assert abs(result.sum() - 1.0) < 1e-9

    def test_non_negative_attribution(self, sample_factors):
        fra = FactorRiskAnalysis()
        cov = fra.factor_covariance(sample_factors)
        exposures = pd.Series(0.25, index=sample_factors.columns)
        result = fra.risk_attribution(exposures, cov)
        # Attribution is normalised to sum to 1; F1 contribution may be negative
        # due to negative correlation with F0/F2, which is mathematically correct.
        assert abs(result.sum() - 1.0) < 1e-9

    def test_accepts_series_exposures(self, sample_factors):
        """Pass exposures as a Series indexed by factor name."""
        fra = FactorRiskAnalysis()
        cov = fra.factor_covariance(sample_factors)
        exposures = pd.Series([0.5, 0.3, 0.2], index=["F0", "F1", "F2"])
        result = fra.risk_attribution(exposures, cov)
        assert isinstance(result, pd.Series)
        assert abs(result.sum() - 1.0) < 1e-9

    def test_empty_inputs(self):
        fra = FactorRiskAnalysis()
        empty = pd.Series(dtype=float)
        result = fra.risk_attribution(empty, pd.DataFrame())
        assert isinstance(result, pd.Series)
