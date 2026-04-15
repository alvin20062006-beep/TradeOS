"""
core.research.portfolio.constraints
====================================
约束条件构建器。

build_constraint(cfg_type, params, n, asset_ids)
  → (build_cvxpy_fn, check_fn)
    build_cvxpy_fn(w: cp.Variable, constraints: list, abs_fn: callable)
    check_fn(w: np.ndarray) → dict of violations
"""

from __future__ import annotations

import numpy as np


# ── Registry ───────────────────────────────────────────────────────────────

CONSTRAINT_REGISTRY: dict[str, dict] = {}


def _register(name: str, doc: str):
    def decorator(fn):
        CONSTRAINT_REGISTRY[name] = {"fn": fn, "__doc__": doc}
        return fn
    return decorator


# ── sum_to_one ─────────────────────────────────────────────────────────────

@_register("sum_to_one", "Σᵢ wᵢ = 1")
def sum_to_one(params: dict, n: int, asset_ids: list[str]):
    def build_cvxpy(w, constraints, abs_fn) -> None:
        constraints.append(sum(w) == 1)

    def check(w: np.ndarray) -> dict[str, float]:
        return {"sum_to_one": float(abs(w.sum() - 1))}

    return build_cvxpy, check


# ── long_only ──────────────────────────────────────────────────────────────

@_register("long_only", "wᵢ ≥ 0")
def long_only(params: dict, n: int, asset_ids: list[str]):
    def build_cvxpy(w, constraints, abs_fn) -> None:
        for w_i in w:
            constraints.append(w_i >= 0)

    def check(w: np.ndarray) -> dict[str, float]:
        neg = w[w < -1e-9]
        return {"long_only": float(abs(neg.min())) if len(neg) else 0.0}

    return build_cvxpy, check


# ── max_weight ─────────────────────────────────────────────────────────────

@_register("max_weight", "wᵢ ≤ limit")
def max_weight(params: dict, n: int, asset_ids: list[str]):
    limit = params["limit"]
    if not (0 < limit <= 1):
        raise ValueError(f"max_weight limit must be in (0, 1], got {limit}")

    def build_cvxpy(w, constraints, abs_fn) -> None:
        for w_i in w:
            constraints.append(w_i <= limit)

    def check(w: np.ndarray) -> dict[str, float]:
        return {"max_weight": float(max(0, w.max() - limit))}

    return build_cvxpy, check


# ── min_weight ─────────────────────────────────────────────────────────────

@_register("min_weight", "wᵢ ≥ limit")
def min_weight(params: dict, n: int, asset_ids: list[str]):
    limit = params["limit"]
    if not (0 <= limit < 1):
        raise ValueError(f"min_weight limit must be in [0, 1), got {limit}")

    def build_cvxpy(w, constraints, abs_fn) -> None:
        for w_i in w:
            constraints.append(w_i >= limit)

    def check(w: np.ndarray) -> dict[str, float]:
        under = w[w < limit - 1e-9]
        return {"min_weight": float(abs(under.min() - limit)) if len(under) else 0.0}

    return build_cvxpy, check


# ── sector_target_exposure ─────────────────────────────────────────────────

@_register(
    "sector_target_exposure",
    "Σ_{i∈sector} wᵢ = target_sector"
)
def sector_target_exposure(params: dict, n: int, asset_ids: list[str]):
    sector_map: dict[str, str] | None = params.get("sector_map")
    targets: dict[str, float] | None = params.get("targets")
    if not sector_map:
        raise ValueError(
            "sector_target_exposure requires sector_map in params: {asset_id -> sector_name}"
        )
    if not targets:
        raise ValueError(
            "sector_target_exposure requires targets in params: {sector_name -> target_weight}"
        )

    sector_groups: dict[str, list[int]] = {}
    for idx, aid in enumerate(asset_ids):
        sector = sector_map.get(aid)
        if sector is not None:
            sector_groups.setdefault(sector, []).append(idx)

    def build_cvxpy(w, constraints, abs_fn) -> None:
        for sector, target in targets.items():
            indices = sector_groups[sector]
            sector_sum = sum(w[i] for i in indices)
            constraints.append(sector_sum == target)

    def check(w: np.ndarray) -> dict[str, float]:
        violations = {}
        for sector, target in targets.items():
            indices = sector_groups[sector]
            total = sum(w[i] for i in indices)
            violations[f"sector_target_{sector}"] = float(abs(total - target))
        return violations

    return build_cvxpy, check


# ── sector_deviation_limit ──────────────────────────────────────────────────

@_register(
    "sector_deviation_limit",
    "|Σ_{i∈sector} wᵢ - b_sector| ≤ max_deviation"
)
def sector_deviation_limit(params: dict, n: int, asset_ids: list[str]):
    sector_map: dict[str, str] | None = params.get("sector_map")
    benchmark_sw: dict[str, float] | None = params.get("benchmark_sector_weights")
    max_dev: float | None = params.get("max_deviation")
    if not sector_map:
        raise ValueError(
            "sector_deviation_limit requires sector_map in params: {asset_id -> sector_name}"
        )
    if not benchmark_sw:
        raise ValueError(
            "sector_deviation_limit requires benchmark_sector_weights in params: {sector_name -> weight}"
        )
    if max_dev is None:
        raise ValueError(
            "sector_deviation_limit requires max_deviation in params: float"
        )

    sector_groups: dict[str, list[int]] = {}
    for idx, aid in enumerate(asset_ids):
        sector = sector_map.get(aid)
        if sector is not None:
            sector_groups.setdefault(sector, []).append(idx)

    def build_cvxpy(w, constraints, abs_fn) -> None:
        for sector, bench in benchmark_sw.items():
            indices = sector_groups[sector]
            dev = abs_fn(sum(w[i] for i in indices) - bench)
            constraints.append(dev <= max_dev)

    def check(w: np.ndarray) -> dict[str, float]:
        violations = {}
        for sector, bench in benchmark_sw.items():
            indices = sector_groups[sector]
            dev = float(abs(sum(w[i] for i in indices) - bench))
            violations[f"sector_dev_{sector}"] = max(0, dev - max_dev)
        return violations

    return build_cvxpy, check


# ── max_turnover ───────────────────────────────────────────────────────────

@_register(
    "max_turnover",
    "Σᵢ |wᵢ - wᵢ_prev| ≤ limit"
)
def max_turnover(params: dict, n: int, asset_ids: list[str]):
    current_weights_dict: dict[str, float] = params["current_weights"]
    limit = params["limit"]
    w_prev = np.array([current_weights_dict.get(aid, 0.0) for aid in asset_ids])

    def build_cvxpy(w, constraints, abs_fn) -> None:
        turnover = sum(abs_fn(w[i] - w_prev[i]) for i in range(n))
        constraints.append(turnover <= limit)

    def check(w: np.ndarray) -> dict[str, float]:
        return {"max_turnover": float(max(0, np.abs(w - w_prev).sum() - limit))}

    return build_cvxpy, check


# ── max_leverage ───────────────────────────────────────────────────────────

@_register("max_leverage", "Σᵢ |wᵢ| ≤ limit")
def max_leverage(params: dict, n: int, asset_ids: list[str]):
    limit = params["limit"]
    if limit <= 0:
        raise ValueError(f"max_leverage limit must be positive, got {limit}")

    def build_cvxpy(w, constraints, abs_fn) -> None:
        total = sum(abs_fn(w_i) for w_i in w)
        constraints.append(total <= limit)

    def check(w: np.ndarray) -> dict[str, float]:
        return {"max_leverage": float(max(0, np.abs(w).sum() - limit))}

    return build_cvxpy, check


# ── tracking_error ─────────────────────────────────────────────────────────

@_register(
    "tracking_error",
    "√((w-b)'Σ(w-b)) ≤ limit"
)
def tracking_error(params: dict, n: int, asset_ids: list[str]):
    benchmark_dict: dict[str, float] = params["benchmark_weights"]
    cov_list: list[list[float]] = params["covariance_matrix"]
    limit = params["limit"]
    b = np.array([benchmark_dict.get(aid, 0.0) for aid in asset_ids])
    cov = np.array(cov_list)

    def build_cvxpy(w, constraints, abs_fn) -> None:
        diff = w - b
        te = (abs_fn(diff) @ cov @ abs_fn(diff)) ** 0.5
        constraints.append(te <= limit)

    def check(w: np.ndarray) -> dict[str, float]:
        diff = w - b
        te = np.sqrt(diff @ cov @ diff)
        return {"tracking_error": float(max(0, te - limit))}

    return build_cvxpy, check


# ── Public API ─────────────────────────────────────────────────────────────

def build_constraint(
    constraint_type: str, params: dict, n: int, asset_ids: list[str]
):
    """返回 (build_cvxpy_fn, check_fn)。"""
    if constraint_type not in CONSTRAINT_REGISTRY:
        raise KeyError(
            f"Unknown constraint '{constraint_type}'. "
            f"Available: {list(CONSTRAINT_REGISTRY.keys())}"
        )
    fn = CONSTRAINT_REGISTRY[constraint_type]["fn"]
    return fn(params, n, asset_ids)


def list_constraints() -> list[str]:
    return list(CONSTRAINT_REGISTRY.keys())
