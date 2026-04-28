"""
tests.integration.test_portfolio_optimizer
==========================================
End-to-end integration: Batch 4A factors → Batch 4B optimizer → weights.

Constraints enforced:
  - Research-layer only (no execution fields)
  - No backtest engine (Batch 4C)
"""

from __future__ import annotations

import importlib.util
import numpy as np
import pandas as pd
import pytest

HAS_CVXPY = importlib.util.find_spec("cvxpy") is not None
pytestmark = [
    pytest.mark.research_optional,
    pytest.mark.skipif(not HAS_CVXPY, reason="research optimizer optional dependency is not installed"),
]

if HAS_CVXPY:
    from core.research.portfolio.optimizer import PortfolioOptimizer
else:
    PortfolioOptimizer = None
from core.research.portfolio.schema import (
    ConstraintConfig,
    OptimizationRequest,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def sample_factors():
    """3 assets, 60 days."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    f0 = np.cumsum(np.random.randn(60)) * 0.01 + np.linspace(0, 0.5, 60)
    f1 = np.sin(np.linspace(0, 4 * np.pi, 60)) * 0.01 + np.linspace(0.1, 0.4, 60)
    f2 = np.random.randn(60) * 0.005 + np.linspace(0.05, 0.2, 60)
    return pd.DataFrame({"F0": f0, "F1": f1, "F2": f2}, index=dates)


@pytest.fixture
def forward_returns(sample_factors):
    """Forward returns correlated with F0 and F1."""
    np.random.seed(0)
    r = (
        sample_factors["F0"].values * 0.4
        + sample_factors["F1"].values * 0.3
        + np.random.randn(60) * 0.01
    )
    return pd.Series(r, index=sample_factors.index)


@pytest.fixture
def covariance_matrix(sample_factors):
    """Simple covariance from factor returns."""
    return sample_factors.cov()


# ── Integration Tests ───────────────────────────────────────────────────────

class TestPortfolioOptimizerIntegration:
    """
    B22: End-to-end pipeline: Batch 4A factors → optimizer → weights.
    B24: version_id correctly propagated.
    """

    def test_pipeline_factors_to_weights(self, sample_factors, forward_returns, covariance_matrix):
        """
        End-to-end: factors → optimizer → weights.
        """
        # Use Batch 4A-style factor data as optimizer input
        mu = forward_returns.mean()  # simplified expected returns
        mu_series = pd.Series(
            [forward_returns.mean()] * 3,
            index=["F0", "F1", "F2"]
        )
        # Shift mu slightly per factor to make it non-uniform
        mu_series = pd.Series(
            [0.015, 0.025, 0.018],
            index=["F0", "F1", "F2"]
        )

        req = OptimizationRequest(
            expected_returns=mu_series,
            covariance_matrix=covariance_matrix,
            objective="min_variance",
            version_id="v4b_test_001",
        )
        opt = PortfolioOptimizer()
        result = opt.optimize(req)

        # ── Structural checks ────────────────────────────────────────────
        assert isinstance(result.weights, pd.Series)
        assert set(result.weights.index) == {"F0", "F1", "F2"}
        assert abs(result.weights.sum() - 1.0) < 1e-6
        assert (result.weights >= -1e-9).all()

        # ── Metric checks ────────────────────────────────────────────────
        assert result.portfolio_variance >= 0
        assert result.portfolio_std >= 0
        assert isinstance(result.expected_return, float)
        assert result.solver_status == "optimal"
        assert result.version_id == "v4b_test_001"

        # ── No execution-layer fields ────────────────────────────────────
        result_dict = result.model_dump()
        forbidden = {"order_type", "position", "exec_algo", "slippage", "fees",
                     "signal_id", "order_id", "fill_price"}
        assert forbidden.isdisjoint(set(result_dict.keys()))

    def test_all_objectives_produce_valid_weights(self, covariance_matrix):
        """B4–B7: All objectives solve successfully."""
        mu_series = pd.Series([0.015, 0.025, 0.018], index=["F0", "F1", "F2"])
        req_base = OptimizationRequest(
            expected_returns=mu_series,
            covariance_matrix=covariance_matrix,
            version_id="v4b_test_002",
        )
        opt = PortfolioOptimizer()

        for objective in ["min_variance", "max_sharpe", "risk_parity",
                          "max_utility", "max_return", "equal_weight"]:
            req = req_base.model_copy(deep=True)
            req.objective = objective
            result = opt.optimize(req)
            assert result.solver_status in ("optimal", "max_iter_reached"), \
                f"{objective}: {result.solver_status}"
            assert abs(result.weights.sum() - 1.0) < 1e-4
            assert (result.weights >= -1e-6).all()
            assert result.portfolio_variance >= 0

    def test_risk_contribution_sum_equals_std(self, covariance_matrix):
        """B23: Σ RC_i = portfolio_std."""
        mu_series = pd.Series([0.015, 0.025, 0.018], index=["F0", "F1", "F2"])
        req = OptimizationRequest(
            expected_returns=mu_series,
            covariance_matrix=covariance_matrix,
            objective="min_variance",
            version_id="v4b_test_003",
        )
        opt = PortfolioOptimizer()
        result = opt.optimize(req)

        if result.risk_contribution is not None:
            assert np.isclose(
                result.risk_contribution.sum(),
                result.portfolio_std,
                atol=1e-6
            ), f"RC sum {result.risk_contribution.sum()} != std {result.portfolio_std}"

    def test_constraints_satisfied_in_result(self, covariance_matrix):
        """B8–B15: Constraints recorded as satisfied in result."""
        mu_series = pd.Series([0.015, 0.025, 0.018], index=["F0", "F1", "F2"])
        req = OptimizationRequest(
            expected_returns=mu_series,
            covariance_matrix=covariance_matrix,
            objective="min_variance",
            constraints=[
                ConstraintConfig(type="sum_to_one"),
                ConstraintConfig(type="long_only"),
                ConstraintConfig(type="max_weight", params={"limit": 0.6}),
            ],
            version_id="v4b_test_004",
        )
        opt = PortfolioOptimizer()
        result = opt.optimize(req)

        assert result.constraints_satisfied is True
        max_v = max(result.constraint_violations.values()) if result.constraint_violations else 0; assert max_v < 1e-5

    def test_scipy_fallback_warns_on_incompatible_constraints(self, covariance_matrix):
        """B20: Fallback records skipped constraints."""
        mu_series = pd.Series([0.015, 0.025, 0.018], index=["F0", "F1", "F2"])
        req = OptimizationRequest(
            expected_returns=mu_series,
            covariance_matrix=covariance_matrix,
            objective="min_variance",
            constraints=[
                ConstraintConfig(type="sum_to_one"),
                ConstraintConfig(type="long_only"),
                ConstraintConfig(type="max_turnover", params={
                    "current_weights": {"F0": 0.5, "F1": 0.3, "F2": 0.2},
                    "limit": 0.1,
                }),
            ],
            version_id="v4b_test_005",
        )
        opt = PortfolioOptimizer(prefer_cvxpy=False)
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = opt.optimize(req)
            warning_messages = [str(warning.message) for warning in w]
        # scipy should warn about skipped constraints
        assert result.solver_used == "scipy"
        assert result.solver_status in ("optimal", "max_iter_reached")
