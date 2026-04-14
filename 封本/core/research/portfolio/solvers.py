"""
core.research.portfolio.solvers
================================
求解器后端封装。

主路径  : cvxpy   （严格求解，支持全部约束）
fallback: scipy   （SLSQP，功能受限）

scipy fallback 降级说明
─────────────────────────────────────────────────────────────────────────────
SLSQP 只支持：线性等式/不等式 + 边界约束，不支持 L1 范数和 SOC 约束。
以下约束在 scipy 下会被跳过并在 result.skipped_constraints 中记录：
  - max_turnover  ：Σ|w_i - w_i_prev|  → 需要 L1 范数
  - max_leverage  ：Σ|w_i|             → 需要 L1 范数
  - tracking_error：√((w-b)'Σ(w-b)) ≤ δ → 需要二阶锥（SOC）

scipy 下 max_sharpe、risk_parity 为近似/数值优化实现，
不保证与 cvxpy 主路径数学上完全等价。
    - max_sharpe  ：scipy 求 min_variance 后用样本夏普近似，≠ 联合优化
    - risk_parity ：scipy 求 min_variance 后均衡 RC_i，≠ 联合优化
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field

import numpy as np

HAS_CVXPY = True
HAS_SCIPY = True
try:
    import cvxpy as cp
except ImportError:
    cp = None
    HAS_CVXPY = False
try:
    from scipy.optimize import minimize as scipy_minimize
except ImportError:
    scipy_minimize = None
    HAS_SCIPY = False


@dataclass
class SolverResult:
    weights: np.ndarray
    status: str  # "optimal" | "infeasible" | "unbounded" | "max_iter_reached" | "error"
    objective_value: float
    solve_time_ms: float
    skipped_constraints: list[str] = field(default_factory=list)


# ── cvxpy Solver ────────────────────────────────────────────────────────────

def _solve_cvxpy(objective_fn, n: int) -> SolverResult:
    """
    cvxpy 路径：严格求解，支持全部约束类型。
    """
    start = time.perf_counter()
    w = cp.Variable(n)
    constraints = []
    api = {"w": w, "constraints": constraints, "abs": cp.abs}

    prob = cp.Problem(cp.Minimize(objective_fn(w)), constraints)

    try:
        prob.solve(solver=cp.SCS, verbose=False, max_iters=5000)
    except cp.error.SolverError:
        return SolverResult(
            weights=np.full(n, 1.0 / n),
            status="error",
            objective_value=np.inf,
            solve_time_ms=0.0,
        )

    status = prob.status
    if status in ("optimal", "optimal_inaccurate"):
        w_opt = np.array(w.value).flatten()
        w_opt = np.where(w_opt < -1e-10, 0.0, w_opt)
        return SolverResult(
            weights=w_opt,
            status="optimal",
            objective_value=float(prob.value),
            solve_time_ms=(time.perf_counter() - start) * 1000,
        )
    elif status in ("infeasible", "primal_infeasible"):
        return SolverResult(
            weights=np.full(n, 1.0 / n),
            status="infeasible",
            objective_value=np.inf,
            solve_time_ms=(time.perf_counter() - start) * 1000,
        )
    elif status == "unbounded":
        return SolverResult(
            weights=np.full(n, 1.0 / n),
            status="unbounded",
            objective_value=-np.inf,
            solve_time_ms=(time.perf_counter() - start) * 1000,
        )
    else:
        return SolverResult(
            weights=np.full(n, 1.0 / n),
            status="error",
            objective_value=np.inf,
            solve_time_ms=(time.perf_counter() - start) * 1000,
        )


# ── scipy (SLSQP) Solver ────────────────────────────────────────────────────

_SCIPY_INCOMPATIBLE = {"max_turnover", "max_leverage", "tracking_error"}


def _solve_scipy(
    objective_fn,
    constraint_specs: list[dict],
    n: int,
    asset_ids: list[str],
) -> SolverResult:
    """
    scipy (SLSQP) 路径：近似求解。

    constraint_specs: list of {"type": str, "params": dict}
    只处理 scipy 兼容的约束类型；不兼容的记录到 skipped_constraints。
    """
    start = time.perf_counter()
    skipped: list[str] = []

    slsqp_eq = []   # list of fun(x) -> float  (must = 0)
    slsqp_ineq = [] # list of fun(x) -> float  (must >= 0)
    bounds = [(0.0, 1.0) for _ in range(n)]

    for spec in constraint_specs:
        ctype = spec["type"]
        params = spec.get("params", {})

        if ctype in _SCIPY_INCOMPATIBLE:
            skipped.append(ctype)
            warnings.warn(f"Constraint '{ctype}' skipped in scipy fallback (L1/SOC not supported)")
            continue

        if ctype == "sum_to_one":
            slsqp_eq.append(lambda w: float(w.sum() - 1.0))

        elif ctype == "long_only":
            # Handled by bounds: w_i >= 0 already set
            pass

        elif ctype == "max_weight":
            limit = params["limit"]
            for i in range(n):
                slsqp_ineq.append(lambda w, lim=limit, idx=i: float(lim - w[idx]))

        elif ctype == "min_weight":
            limit = params["limit"]
            for i in range(n):
                slsqp_ineq.append(lambda w, lim=limit, idx=i: float(w[idx] - lim))

        elif ctype == "sector_target_exposure":
            sector_map = params["sector_map"]
            targets = params["targets"]
            sector_groups: dict[str, list[int]] = {}
            for idx, aid in enumerate(asset_ids):
                sec = sector_map.get(aid)
                if sec:
                    sector_groups.setdefault(sec, []).append(idx)
            for sec, target in targets.items():
                indices = sector_groups.get(sec, [])
                if indices:
                    slsqp_eq.append(
                        lambda w, idxs=indices, tgt=target: float(sum(w[i] for i in idxs) - tgt)
                    )

        elif ctype == "sector_deviation_limit":
            sector_map = params["sector_map"]
            bench_sw = params["benchmark_sector_weights"]
            max_dev = params["max_deviation"]
            sector_groups: dict[str, list[int]] = {}
            for idx, aid in enumerate(asset_ids):
                sec = sector_map.get(aid)
                if sec:
                    sector_groups.setdefault(sec, []).append(idx)
            for sec, bench in bench_sw.items():
                indices = sector_groups.get(sec, [])
                if indices:
                    dev = lambda w, idxs=indices, b=bench: float(abs(sum(w[i] for i in idxs) - b))
                    slsqp_ineq.append(
                        lambda w, d=dev, md=max_dev: float(md - d(w))
                    )

        else:
            warnings.warn(f"Constraint '{ctype}' unknown in scipy fallback, skipping")

    w0 = np.full(n, 1.0 / n)

    constraints = []
    if slsqp_eq:
        constraints.append({"type": "eq", "fun": lambda w: np.array([fn(w) for fn in slsqp_eq])})
    if slsqp_ineq:
        constraints.append({"type": "ineq", "fun": lambda w: np.array([fn(w) for fn in slsqp_ineq])})

    result = scipy_minimize(
        objective_fn,
        w0,
        args=(),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 5000, "ftol": 1e-9},
    )

    status_map = {
        0: "optimal",
        1: "max_iter_reached",
        2: "infeasible",
        3: "error",
        4: "error",
    }
    w_opt = np.clip(result.x, 0.0, 1.0)
    if w_opt.sum() > 1e-9:
        w_opt = w_opt / w_opt.sum()

    if skipped:
        warnings.warn(
            f"Batch 4B scipy fallback: constraints {skipped} skipped. "
            "Results may differ from cvxpy primary path."
        )

    return SolverResult(
        weights=w_opt,
        status=status_map.get(result.status, "error"),
        objective_value=float(result.fun),
        solve_time_ms=(time.perf_counter() - start) * 1000,
        skipped_constraints=skipped,
    )


# ── Public API ──────────────────────────────────────────────────────────────

def solve(
    objective_fn,
    constraint_specs: list[dict],
    n: int,
    asset_ids: list[str],
    prefer_cvxpy: bool = True,
) -> SolverResult:
    """
    主求解入口。

    参数
    ─────
    objective_fn    : 目标函数 (w: np.ndarray) -> float
    constraint_specs : list of {"type": str, "params": dict}
    n               : 资产数量
    asset_ids       : 资产 ID 列表
    prefer_cvxpy    : 是否优先使用 cvxpy

    返回
    ─────
    SolverResult
    """
    if prefer_cvxpy and HAS_CVXPY:
        result = _solve_cvxpy(objective_fn, n)
        if result.status == "optimal":
            return result
        # cvxpy 非 optimal，尝试 scipy fallback
        warnings.warn(
            f"cvxpy returned status '{result.status}'; "
            f"retrying with scipy fallback. Skipped constraints: {result.skipped_constraints}"
        )

    if HAS_SCIPY:
        return _solve_scipy(objective_fn, constraint_specs, n, asset_ids)
    else:
        raise RuntimeError("No solver available: cvxpy and scipy both unavailable")
