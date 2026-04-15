"""
tests.unit.test_objectives
===========================
"""

import numpy as np
import pandas as pd
import pytest

from core.research.portfolio.objectives import (
    get_objective,
    list_objectives,
    risk_contribution,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def sample_mu():
    return np.array([0.01, 0.02, 0.015])


@pytest.fixture
def sample_cov():
    return np.array([
        [0.010, 0.002, 0.001],
        [0.002, 0.020, 0.003],
        [0.001, 0.003, 0.015],
    ])


@pytest.fixture
def equal_weights():
    return np.array([1/3, 1/3, 1/3])


@pytest.fixture
def sample_series():
    return pd.Series([1/3, 1/3, 1/3], index=["A", "B", "C"])


# ── Registry ─────────────────────────────────────────────────────────────────

class TestObjectiveRegistry:
    def test_list_objectives(self):
        names = list_objectives()
        assert "min_variance" in names
        assert "max_sharpe" in names
        assert "risk_parity" in names
        assert "max_utility" in names
        assert "max_return" in names
        assert "equal_weight" in names

    def test_get_objective_valid(self):
        fn = get_objective("min_variance")
        assert callable(fn)

    def test_get_objective_invalid(self):
        with pytest.raises(KeyError):
            get_objective("invalid_objective")


# ── Objective Functions ─────────────────────────────────────────────────────

class TestObjectiveValues:
    def test_min_variance(self, sample_mu, sample_cov, equal_weights):
        fn = get_objective("min_variance")
        val = fn(equal_weights, sample_mu, sample_cov, lam=1.0)
        assert isinstance(val, float)
        assert val >= 0

    def test_min_variance_value(self, sample_mu, sample_cov, equal_weights):
        fn = get_objective("min_variance")
        val = fn(equal_weights, sample_mu, sample_cov, lam=1.0)
        assert isinstance(val, float)
        assert val >= 0

    def test_max_return(self, sample_mu, sample_cov, equal_weights):
        fn = get_objective("max_return")
        val = fn(equal_weights, sample_mu, sample_cov, lam=1.0)
        # max_return should concentrate in asset 1 (highest return)
        max_ret = np.array([0.0, 1.0, 0.0])
        max_ret_val = fn(max_ret, sample_mu, sample_cov, lam=1.0)
        assert max_ret_val <= val

    def test_max_utility(self, sample_mu, sample_cov, equal_weights):
        fn = get_objective("max_utility")
        val = fn(equal_weights, sample_mu, sample_cov, lam=1.0)
        assert isinstance(val, float)

    def test_max_utility_lambda_zero(self, sample_mu, sample_cov, equal_weights):
        fn = get_objective("max_utility")
        val0 = fn(equal_weights, sample_mu, sample_cov, lam=0.0)
        val1 = fn(equal_weights, sample_mu, sample_cov, lam=1.0)
        assert val0 != val1  # different risk aversion

    def test_equal_weight(self, sample_mu, sample_cov, equal_weights):
        fn = get_objective("equal_weight")
        val = fn(equal_weights, sample_mu, sample_cov, lam=1.0)
        assert val == 0.0


# ── Risk Contribution ────────────────────────────────────────────────────────

class TestRiskContribution:
    def test_risk_contribution_sum(self, sample_series):
        cov_df = pd.DataFrame(
            [[0.010, 0.002, 0.001], [0.002, 0.020, 0.003], [0.001, 0.003, 0.015]],
            index=["A", "B", "C"],
            columns=["A", "B", "C"],
        )
        w = pd.Series([0.5, 0.3, 0.2], index=["A", "B", "C"])
        rc = risk_contribution(w, cov_df)
        assert isinstance(rc, pd.Series)
        assert abs(rc.sum() - np.sqrt(w @ cov_df.values @ w)) < 1e-9
        assert set(rc.index) == set(w.index)

    def test_risk_contribution_all_zero_weights(self, sample_series):
        cov_df = pd.DataFrame(
            [[0.01, 0.002, 0.001], [0.002, 0.02, 0.003], [0.001, 0.003, 0.015]],
            index=["A", "B", "C"],
            columns=["A", "B", "C"],
        )
        w = pd.Series([0.0, 0.0, 0.0], index=["A", "B", "C"])
        rc = risk_contribution(w, cov_df)
        assert rc.sum() == 0.0

    def test_risk_contribution_single_asset(self):
        cov_df = pd.DataFrame([[0.01]], index=["A"], columns=["A"])
        w = pd.Series([1.0], index=["A"])
        rc = risk_contribution(w, cov_df)
        assert np.isclose(rc.iloc[0], np.sqrt(0.01))
