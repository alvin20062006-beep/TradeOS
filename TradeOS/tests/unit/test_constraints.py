"""
tests.unit.test_constraints
============================
"""

import numpy as np
import pytest

from core.research.portfolio.constraints import build_constraint, list_constraints


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def n(): return 4

@pytest.fixture
def asset_ids(): return ["A", "B", "C", "D"]

@pytest.fixture
def w_equal(): return np.array([0.25, 0.25, 0.25, 0.25])


# ── Registry ────────────────────────────────────────────────────────────────

class TestConstraintRegistry:
    def test_list_constraints(self):
        names = list_constraints()
        assert "sum_to_one" in names
        assert "long_only" in names
        assert "max_weight" in names
        assert "min_weight" in names
        assert "sector_target_exposure" in names
        assert "sector_deviation_limit" in names
        assert "max_turnover" in names
        assert "max_leverage" in names
        assert "tracking_error" in names

    def test_unknown_constraint_raises(self, n, asset_ids):
        with pytest.raises(KeyError):
            build_constraint("unknown_type", {}, n, asset_ids)


# ── Individual Constraint Check Functions ──────────────────────────────────

class TestSumToOne:
    def test_equal_weights_satisfied(self, w_equal):
        _, check_fn = build_constraint("sum_to_one", {}, 4, ["A", "B", "C", "D"])
        violations = check_fn(w_equal)
        assert violations["sum_to_one"] < 1e-9

    def test_unequal_weights_violated(self):
        _, check_fn = build_constraint("sum_to_one", {}, 4, ["A", "B", "C", "D"])
        w = np.array([0.6, 0.22, 0.1, 0.09])
        violations = check_fn(w)
        assert violations["sum_to_one"] > 1e-9


class TestLongOnly:
    def test_positive_weights_satisfied(self, w_equal):
        _, check_fn = build_constraint("long_only", {}, 4, ["A", "B", "C", "D"])
        violations = check_fn(w_equal)
        assert violations["long_only"] == 0.0

    def test_negative_weights_violated(self):
        _, check_fn = build_constraint("long_only", {}, 4, ["A", "B", "C", "D"])
        w = np.array([0.6, -0.1, 0.3, 0.2])
        violations = check_fn(w)
        assert violations["long_only"] > 1e-6


class TestMaxWeight:
    def test_within_limit(self):
        _, check_fn = build_constraint("max_weight", {"limit": 0.5}, 4, ["A", "B", "C", "D"])
        w = np.array([0.3, 0.3, 0.2, 0.2])
        assert check_fn(w)["max_weight"] < 1e-9

    def test_exceeds_limit(self):
        _, check_fn = build_constraint("max_weight", {"limit": 0.3}, 4, ["A", "B", "C", "D"])
        w = np.array([0.4, 0.2, 0.2, 0.2])
        assert check_fn(w)["max_weight"] > 1e-6

    def test_invalid_limit_raises(self):
        with pytest.raises(ValueError, match="limit"):
            build_constraint("max_weight", {"limit": 1.5}, 4, ["A", "B", "C", "D"])


class TestMinWeight:
    def test_above_limit(self):
        _, check_fn = build_constraint("min_weight", {"limit": 0.1}, 4, ["A", "B", "C", "D"])
        w = np.array([0.3, 0.3, 0.2, 0.2])
        assert check_fn(w)["min_weight"] == 0.0

    def test_below_limit(self):
        _, check_fn = build_constraint("min_weight", {"limit": 0.3}, 4, ["A", "B", "C", "D"])
        w = np.array([0.1, 0.3, 0.3, 0.3])
        assert check_fn(w)["min_weight"] > 1e-6


class TestSectorTargetExposure:
    def test_sector_target_satisfied(self):
        sector_map = {"A": "X", "B": "X", "C": "Y", "D": "Y"}
        targets = {"X": 0.6, "Y": 0.4}
        _, check_fn = build_constraint(
            "sector_target_exposure",
            {"sector_map": sector_map, "targets": targets},
            4, ["A", "B", "C", "D"]
        )
        w = np.array([0.3, 0.3, 0.2, 0.2])
        violations = check_fn(w)
        assert violations["sector_target_X"] < 1e-9
        assert violations["sector_target_Y"] < 1e-9

    def test_sector_target_violated(self):
        sector_map = {"A": "X", "B": "X", "C": "Y", "D": "Y"}
        targets = {"X": 0.6, "Y": 0.4}
        _, check_fn = build_constraint(
            "sector_target_exposure",
            {"sector_map": sector_map, "targets": targets},
            4, ["A", "B", "C", "D"]
        )
        w = np.array([0.6, 0.22, 0.1, 0.09])  # X=0.7, Y=0.3
        violations = check_fn(w)
        assert violations["sector_target_X"] > 1e-6


class TestSectorDeviationLimit:
    def test_within_deviation(self):
        sector_map = {"A": "X", "B": "X", "C": "Y", "D": "Y"}
        bench_sw = {"X": 0.5, "Y": 0.5}
        _, check_fn = build_constraint(
            "sector_deviation_limit",
            {"sector_map": sector_map, "benchmark_sector_weights": bench_sw, "max_deviation": 0.1},
            4, ["A", "B", "C", "D"]
        )
        w = np.array([0.4, 0.1, 0.4, 0.1])  # X=0.5, Y=0.5, dev=0
        violations = check_fn(w)
        assert max(violations.values()) < 1e-9

    def test_exceeds_deviation(self):
        sector_map = {"A": "X", "B": "X", "C": "Y", "D": "Y"}
        bench_sw = {"X": 0.5, "Y": 0.5}
        _, check_fn = build_constraint(
            "sector_deviation_limit",
            {"sector_map": sector_map, "benchmark_sector_weights": bench_sw, "max_deviation": 0.1},
            4, ["A", "B", "C", "D"]
        )
        w = np.array([0.7, 0.0, 0.2, 0.1])  # X=0.7, dev=0.2 > 0.1
        violations = check_fn(w)
        assert violations["sector_dev_X"] > 0.0


class TestMaxTurnover:
    def test_within_limit(self):
        _, check_fn = build_constraint(
            "max_turnover",
            {"current_weights": {"A": 0.3, "B": 0.3, "C": 0.2, "D": 0.2}, "limit": 0.2},
            4, ["A", "B", "C", "D"]
        )
        w = np.array([0.25, 0.25, 0.25, 0.25])
        assert check_fn(w)["max_turnover"] == 0.0

    def test_exceeds_limit(self):
        _, check_fn = build_constraint(
            "max_turnover",
            {"current_weights": {"A": 0.8, "B": 0.1, "C": 0.05, "D": 0.05}, "limit": 0.2},
            4, ["A", "B", "C", "D"]
        )
        w = np.array([0.25, 0.25, 0.25, 0.25])
        assert check_fn(w)["max_turnover"] > 1e-6


class TestMaxLeverage:
    def test_within_limit(self, w_equal):
        _, check_fn = build_constraint("max_leverage", {"limit": 1.2}, 4, ["A", "B", "C", "D"])
        assert check_fn(w_equal)["max_leverage"] == 0.0

    def test_exceeds_limit(self):
        _, check_fn = build_constraint("max_leverage", {"limit": 0.8}, 4, ["A", "B", "C", "D"])
        w = np.array([0.3, 0.3, 0.3, 0.3])  # sum=1.2 > 0.8
        assert check_fn(w)["max_leverage"] > 1e-6

    def test_invalid_limit_raises(self):
        with pytest.raises(ValueError, match="limit"):
            build_constraint("max_leverage", {"limit": -0.5}, 4, ["A", "B", "C", "D"])


class TestTrackingError:
    def test_within_limit(self):
        cov_list = [
            [0.010, 0.002, 0.001, 0.000],
            [0.002, 0.020, 0.003, 0.001],
            [0.001, 0.003, 0.015, 0.002],
            [0.000, 0.001, 0.002, 0.010],
        ]
        _, check_fn = build_constraint(
            "tracking_error",
            {
                "benchmark_weights": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
                "covariance_matrix": cov_list,
                "limit": 0.05,
            },
            4, ["A", "B", "C", "D"]
        )
        w = np.array([0.25, 0.25, 0.25, 0.25])  # identical to benchmark → TE=0
        assert check_fn(w)["tracking_error"] < 1e-9

    def test_exceeds_limit(self):
        cov_list = [
            [0.010, 0.002, 0.001, 0.000],
            [0.002, 0.020, 0.003, 0.001],
            [0.001, 0.003, 0.015, 0.002],
            [0.000, 0.001, 0.002, 0.010],
        ]
        _, check_fn = build_constraint(
            "tracking_error",
            {
                "benchmark_weights": {"A": 0.8, "B": 0.1, "C": 0.1, "D": 0.0},
                "covariance_matrix": cov_list,
                "limit": 0.01,
            },
            4, ["A", "B", "C", "D"]
        )
        w = np.array([0.0, 0.0, 0.5, 0.5])  # very different from benchmark
        assert check_fn(w)["tracking_error"] > 0.01
