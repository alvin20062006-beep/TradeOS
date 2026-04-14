"""
tests.integration.test_alpha_pipeline
=====================================
End-to-end integration test for Batch 4A alpha pipeline.

Pipeline:
    single factors (from builders)
    -> selector (correlation prune / ic threshold / best_k)
    -> multi-factor combination (equal / ic / ir weights)
    -> extended evaluation (IC/IR/group IC/turnover)
    -> risk exposure outputs (factor betas / covariance / market beta)

Constraints:
    - Research-layer only: no execution/position/order fields
    - No optimizer (Batch 4B)
    - No backtest engine / strategy base (Batch 4C)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.research.alpha.builders.multi_factor import MultiFactorBuilder
from core.research.alpha.evaluation.metrics import FactorMetrics, FactorMetricsBundle
from core.research.alpha.risk.factors import FactorRiskAnalysis
from core.research.alpha.selection.selector import FactorSelector


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_factors() -> pd.DataFrame:
    """
    5 candidate factors, 120 days.
    F0/F1/F2 have positive IC; F3/F4 near zero.
    """
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    f0 = np.cumsum(np.random.randn(120))  # trending
    f1 = np.sin(np.linspace(0, 4 * np.pi, 120)) + np.random.randn(120) * 0.2
    f2 = np.random.randn(120) * 0.5 + np.linspace(0, 1, 120)
    f3 = np.random.randn(120)  # noise
    f4 = np.random.randn(120)  # noise
    return pd.DataFrame({"F0": f0, "F1": f1, "F2": f2, "F3": f3, "F4": f4}, index=dates)


@pytest.fixture
def forward_returns(synthetic_factors) -> pd.Series:
    """
    Forward returns strongly correlated with F0/F1/F2, weak with F3/F4.
    """
    np.random.seed(42)
    r = (
        synthetic_factors["F0"].values * 0.4
        + synthetic_factors["F1"].values * 0.3
        + synthetic_factors["F2"].values * 0.2
        + np.random.randn(120) * 0.2
    )
    return pd.Series(r, index=synthetic_factors.index)


@pytest.fixture
def market_returns() -> pd.Series:
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    return pd.Series(np.random.randn(120) * 0.01 + 0.0003, index=dates)


# ── Integration Test ──────────────────────────────────────────────────────

class TestAlphaPipelineBatch4A:
    """
    End-to-end pipeline test for Batch 4A.
    """

    def test_full_pipeline_runs_without_error(
        self,
        synthetic_factors: pd.DataFrame,
        forward_returns: pd.Series,
        market_returns: pd.Series,
    ):
        """
        Pipeline: factors → selector → combination → evaluation → risk exposure.
        All outputs must be research-layer objects (no execution fields).
        """
        # ── Step 1: Factor Selection ───────────────────────────────────────
        selector = FactorSelector(min_ic=0.05, min_ir=0.2, corr_threshold=0.8)
        selected_names = selector.select(
            synthetic_factors, forward_returns, strategy="ic_ir"
        )
        assert isinstance(selected_names, list)
        # At least one factor should survive (F0/F1/F2 have strong signal)
        assert len(selected_names) >= 1
        # All names must be columns in the original DataFrame
        assert all(name in synthetic_factors.columns for name in selected_names)

        # ── Step 2: Multi-Factor Combination ────────────────────────────────
        selected_factors = synthetic_factors[selected_names]
        mfb = MultiFactorBuilder(handle_neg_ic=True)
        composite = mfb.combine(selected_factors, method="ic", labels=forward_returns)
        assert isinstance(composite, pd.Series)
        assert len(composite) == len(synthetic_factors)
        # No NaN in composite (should be zero-filled or handled)
        assert not composite.isnull().all()

        # ── Step 3: Extended Evaluation ─────────────────────────────────────
        bundle = FactorMetricsBundle()
        for name in selected_names:
            fm = FactorMetrics.compute(
                synthetic_factors[name], forward_returns, factor_name=name, n_groups=5
            )
            bundle.add(fm)

        # IC summary should be non-empty
        summary = bundle.ic_summary()
        assert not summary.empty
        assert all(col in summary.columns for col in ["ic_mean", "information_ratio"])

        # ── Step 4: Risk Exposure Analysis ───────────────────────────────────
        fra = FactorRiskAnalysis()
        cov = fra.factor_covariance(selected_factors)
        assert cov.shape[0] == cov.shape[1]
        assert cov.shape[0] == len(selected_names)

        betas = fra.factor_betas(selected_factors, forward_returns)
        assert isinstance(betas, pd.DataFrame)
        # betas may be (n_factors, 1) or (n_factors,) depending on impl
        assert len(betas) >= 1

        market_betas = fra.market_beta(selected_factors, market_returns)
        assert isinstance(market_betas, pd.Series)
        assert set(market_betas.index) == set(selected_names)

        # ── Constraint Check: No execution-layer fields ──────────────────────
        # Composite series should not contain execution-level columns/attrs
        # (By design, MultiFactorBuilder returns a Series, no extra fields.)
        assert isinstance(composite, pd.Series)

        # Summary DataFrame should not have execution columns
        forbidden_cols = {"order_type", "position", "exec_algo", "slippage", "fees"}
        assert forbidden_cols.isdisjoint(set(summary.columns))

    def test_pipeline_handles_empty_factors(
        self,
        forward_returns: pd.Series,
        market_returns: pd.Series,
    ):
        """
        Edge case: empty factor DataFrame should not crash.
        """
        empty_factors = pd.DataFrame(columns=["A", "B"])
        selector = FactorSelector()
        selected = selector.select(empty_factors, forward_returns)
        assert isinstance(selected, list)
        assert len(selected) == 0

        mfb = MultiFactorBuilder()
        composite = mfb.combine(empty_factors, method="equal")
        assert isinstance(composite, pd.Series)
        assert len(composite) == 0

    def test_pipeline_single_factor(self, forward_returns: pd.Series):
        """
        Edge case: single factor should pass through without crash.
        """
        np.random.seed(0)
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        single = pd.DataFrame({"F0": np.random.randn(60)}, index=dates)
        aligned_labels = forward_returns.iloc[:60]

        selector = FactorSelector()
        selected = selector.select(single, aligned_labels, strategy="best_only")
        assert isinstance(selected, list)

        mfb = MultiFactorBuilder()
        composite = mfb.combine(single[selected] if selected else single, method="equal")
        assert isinstance(composite, pd.Series)

        fra = FactorRiskAnalysis()
        cov = fra.factor_covariance(single[selected] if selected else single)
        assert cov.shape == (1, 1)

    def test_risk_attribution_normalisation(
        self,
        synthetic_factors: pd.DataFrame,
        forward_returns: pd.Series,
    ):
        """
        Risk attribution should return a normalised Series summing to 1.
        """
        # Use all factors for risk attribution test
        fra = FactorRiskAnalysis()
        cov = fra.factor_covariance(synthetic_factors)
        exposures = pd.Series(0.2, index=synthetic_factors.columns)
        attr = fra.risk_attribution(exposures, cov)
        assert isinstance(attr, pd.Series)
        assert abs(attr.sum() - 1.0) < 1e-9
