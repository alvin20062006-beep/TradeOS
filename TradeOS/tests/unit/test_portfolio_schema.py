"""
tests.unit.test_portfolio_schema
==================================
"""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from core.research.portfolio.schema import (
    ConstraintConfig,
    OptimizationRequest,
    OptimizationResult,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_mu():
    return pd.Series([0.01, 0.02, 0.015], index=["A", "B", "C"])


@pytest.fixture
def valid_cov():
    return pd.DataFrame(
        [[0.01, 0.002, 0.001], [0.002, 0.02, 0.003], [0.001, 0.003, 0.015]],
        index=["A", "B", "C"],
        columns=["A", "B", "C"],
    )


@pytest.fixture
def valid_request(valid_mu, valid_cov):
    return OptimizationRequest(
        expected_returns=valid_mu,
        covariance_matrix=valid_cov,
        objective="min_variance",
    )


# ── OptimizationRequest ──────────────────────────────────────────────────────

class TestOptimizationRequest:
    def test_valid_request(self, valid_request):
        assert valid_request.objective == "min_variance"
        assert len(valid_request.constraints) == 2

    def test_dict_coercion(self, valid_mu, valid_cov):
        req = OptimizationRequest(
            expected_returns=valid_mu.to_dict(),
            covariance_matrix=valid_cov,
        )
        assert isinstance(req.expected_returns, pd.Series)

    def test_index_mismatch_raises(self, valid_mu, valid_cov):
        bad_mu = pd.Series([0.01, 0.02], index=["A", "D"])
        with pytest.raises(ValueError, match="index.*!=.*index"):
            OptimizationRequest(expected_returns=bad_mu, covariance_matrix=valid_cov)

    def test_non_square_cov_raises(self, valid_mu):
        bad_cov = pd.DataFrame(
            [[0.01, 0.002], [0.002, 0.02], [0.001, 0.003]],
            index=["A", "B", "C"],
            columns=["A", "B"],
        )
        with pytest.raises(ValueError, match="square"):
            OptimizationRequest(expected_returns=valid_mu, covariance_matrix=bad_cov)

    def test_non_symmetric_cov_raises(self, valid_mu):
        bad_cov = pd.DataFrame(
            [[0.01, 0.002, 0.001], [0.003, 0.02, 0.003], [0.001, 0.003, 0.015]],
            index=["A", "B", "C"],
            columns=["A", "B", "C"],
        )
        with pytest.raises(ValueError, match="symmetric"):
            OptimizationRequest(expected_returns=valid_mu, covariance_matrix=bad_cov)

    def test_negative_definite_cov_raises(self, valid_mu):
        bad_cov = pd.DataFrame(
            [[0.01, 0.05, 0.001], [0.05, 0.02, 0.003], [0.001, 0.003, 0.015]],
            index=["A", "B", "C"],
            columns=["A", "B", "C"],
        )
        with pytest.raises(ValueError, match="positive semi-definite"):
            OptimizationRequest(expected_returns=valid_mu, covariance_matrix=bad_cov)

    def test_current_weights_index_mismatch_raises(self, valid_mu, valid_cov):
        bad_w = pd.Series([0.3, 0.4], index=["A", "D"])
        with pytest.raises(ValueError, match="current_weights"):
            OptimizationRequest(
                expected_returns=valid_mu,
                covariance_matrix=valid_cov,
                current_weights=bad_w,
            )

    def test_benchmark_weights_index_mismatch_raises(self, valid_mu, valid_cov):
        bad_b = pd.Series([0.3, 0.4], index=["A", "D"])
        with pytest.raises(ValueError, match="benchmark_weights"):
            OptimizationRequest(
                expected_returns=valid_mu,
                covariance_matrix=valid_cov,
                benchmark_weights=bad_b,
            )

    def test_empty_raises(self, valid_cov):
        with pytest.raises(ValueError):
            OptimizationRequest(
                expected_returns=pd.Series([], dtype=float),
                covariance_matrix=pd.DataFrame(),
            )

    def test_single_asset_valid(self):
        """单资产输入应通过验证。"""
        mu = pd.Series([0.01], index=["A"])
        cov = pd.DataFrame([[0.01]], index=["A"], columns=["A"])
        req = OptimizationRequest(expected_returns=mu, covariance_matrix=cov)
        assert len(req.expected_returns) == 1

    def test_default_constraints(self, valid_mu, valid_cov):
        req = OptimizationRequest(expected_returns=valid_mu, covariance_matrix=valid_cov)
        assert len(req.constraints) == 2
        assert req.constraints[0].type == "sum_to_one"
        assert req.constraints[1].type == "long_only"


# ── OptimizationResult ──────────────────────────────────────────────────────

class TestOptimizationResult:
    def test_valid_result(self, valid_request):
        result = OptimizationResult(
            weights=pd.Series([0.3, 0.4, 0.3], index=["A", "B", "C"]),
            objective_value=0.005,
            solver_status="optimal",
            solver_used="cvxpy",
            solve_time_ms=12.5,
            portfolio_variance=0.005,
            portfolio_std=0.071,
            expected_return=0.017,
            constraints_satisfied=True,
        )
        assert result.solver_used == "cvxpy"
        assert result.constraints_satisfied is True

    def test_result_with_sharpe(self, valid_request):
        result = OptimizationResult(
            weights=pd.Series([0.3, 0.4, 0.3], index=["A", "B", "C"]),
            objective_value=-0.2,
            solver_status="optimal",
            solver_used="cvxpy",
            solve_time_ms=12.5,
            portfolio_variance=0.005,
            portfolio_std=0.071,
            expected_return=0.017,
            sharpe_ratio=0.24,
            constraints_satisfied=True,
        )
        assert result.sharpe_ratio == 0.24

    def test_result_with_violations(self, valid_request):
        result = OptimizationResult(
            weights=pd.Series([0.3, 0.4, 0.3], index=["A", "B", "C"]),
            objective_value=0.005,
            solver_status="optimal",
            solver_used="cvxpy",
            solve_time_ms=12.5,
            portfolio_variance=0.005,
            portfolio_std=0.071,
            expected_return=0.017,
            constraints_satisfied=False,
            constraint_violations={"max_weight": 0.1},
        )
        assert result.constraints_satisfied is False
        assert result.constraint_violations["max_weight"] == 0.1

    def test_result_negative_variance_raises(self, valid_request):
        with pytest.raises(ValidationError):
            OptimizationResult(
                weights=pd.Series([0.3, 0.4, 0.3], index=["A", "B", "C"]),
                objective_value=0.005,
                solver_status="optimal",
                solver_used="cvxpy",
                solve_time_ms=12.5,
                portfolio_variance=-0.001,  # negative → invalid
                portfolio_std=0.071,
                expected_return=0.017,
                constraints_satisfied=True,
            )
