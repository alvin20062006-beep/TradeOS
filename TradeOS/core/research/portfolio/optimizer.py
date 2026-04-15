"""
core.research.portfolio.optimizer
===================================
PortfolioOptimizer 主入口。
接受 OptimizationRequest，返回 OptimizationResult（研究层）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import cvxpy as cp  # noqa: E402  (module-level for _cp_quad access)

from core.research.portfolio.constraints import build_constraint
from core.research.portfolio.objectives import get_objective, risk_contribution as _rc
from core.research.portfolio.schema import (
    ConstraintConfig,
    OptimizationRequest,
    OptimizationResult,
)
from core.research.portfolio import solvers


# ── Helpers ─────────────────────────────────────────────────────────────────

def _cp_quad(w, cov) -> "cp.Expression":
    """二次型 w' Σ w（cvxpy 版本）。"""
    return cp.quad_form(w, cov)


def _build_scipy_specs(configs: list[ConstraintConfig]) -> list[dict]:
    """scipy SLSQP 约束格式。L1/SOC 类约束记录为 skipped。"""
    SKIPPED = {"max_turnover", "max_leverage", "tracking_error"}
    specs = []
    for cfg in configs:
        if cfg.type in SKIPPED:
            specs.append({"type": cfg.type, "params": cfg.params, "_skipped": True})
        elif cfg.type in (
            "sum_to_one", "long_only", "max_weight", "min_weight",
            "sector_target_exposure", "sector_deviation_limit",
        ):
            specs.append({"type": cfg.type, "params": cfg.params})
    return specs


def _build_cvxpy_constraints(configs, w_var, constraints, n, asset_ids):
    """添加 cvxpy 约束，返回 check 函数列表。"""
    checkers = []
    for cfg in configs:
        build_fn, check_fn = build_constraint(cfg.type, cfg.params, n, asset_ids)
        build_fn(w_var, constraints, cp.abs)
        checkers.append(check_fn)
    return checkers


# ── Objective builders ──────────────────────────────────────────────────────

def _build_objective(objective: str, mu: np.ndarray, cov: np.ndarray, lam: float):
    """
    返回 (cp_fn, np_fn)：
      cp_fn: w -> cp.Expression
      np_fn: w -> float
    """
    n = len(mu)

    if objective == "max_sharpe":
        # Guard: if expected returns are all zero or near-zero, fall back to min_variance
        if np.abs(mu).max() < 1e-9:
            # Return min_variance instead to avoid division by zero
            def cp_fn(w):
                return _cp_quad(w, cov)

            def np_fn(w):
                return float(w @ cov @ w)
            return cp_fn, np_fn

        def cp_fn(w):
            port_ret = mu @ w
            port_var = _cp_quad(w, cov)
            return -port_ret / (cp.sqrt(port_var) + 1e-12)

        def np_fn(w):
            port_ret = float(w @ mu)
            port_var = float(w @ cov @ w)
            return -port_ret / (port_var ** 0.5 + 1e-12)
        return cp_fn, np_fn

    elif objective == "min_variance":
        def cp_fn(w):
            return _cp_quad(w, cov)

        def np_fn(w):
            return float(w @ cov @ w)
        return cp_fn, np_fn

    elif objective == "risk_parity":
        def cp_fn(w):
            port_std = cp.sqrt(_cp_quad(w, cov)) + 1e-12
            marginal = cov @ w  # numpy constant @ cp.Expression
            rc = cp.multiply(w, marginal) / port_std
            target = 1.0 / n
            return cp.sum((rc - target) ** 2)

        def np_fn(w):
            port_var = float(w @ cov @ w)
            port_std = max(port_var ** 0.5, 1e-12)
            rc = w * (cov @ w) / port_std
            target = 1.0 / n
            return float(np.sum((rc - target) ** 2))
        return cp_fn, np_fn

    elif objective == "max_utility":
        def cp_fn(w):
            return -(mu @ w - 0.5 * lam * _cp_quad(w, cov))

        def np_fn(w):
            return float(-(w @ mu - 0.5 * lam * (w @ cov @ w)))
        return cp_fn, np_fn

    elif objective == "max_return":
        def cp_fn(w):
            return -mu @ w

        def np_fn(w):
            return float(-w @ mu)
        return cp_fn, np_fn

    elif objective == "equal_weight":
        return None, None

    else:
        raise ValueError(f"Unknown objective: {objective}")


# ── PortfolioOptimizer ─────────────────────────────────────────────────────

class PortfolioOptimizer:
    """研究层组合优化器。"""

    def __init__(self, prefer_cvxpy: bool = True):
        self.prefer_cvxpy = prefer_cvxpy

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        mu = request.expected_returns.values.astype(float)
        cov = request.covariance_matrix.values.astype(float)
        n = len(mu)
        lam = request.risk_aversion
        asset_ids = list(request.expected_returns.index)

        # Initialise so Python knows w_arr is defined at module scope
        w_arr = np.full(n, 1.0 / n)
        solver_used = "equal_weight"
        status = "optimal"
        solve_time = 0.0

        if request.objective != "equal_weight":
            cp_obj_fn, np_obj_fn = _build_objective(
                request.objective, mu, cov, lam
            )

            if self.prefer_cvxpy and solvers.HAS_CVXPY:
                w_var = cp.Variable(n)
                cvx_constraints = []
                checkers = _build_cvxpy_constraints(
                    request.constraints, w_var, cvx_constraints, n, asset_ids
                )

                prob = cp.Problem(cp.Minimize(cp_obj_fn(w_var)), cvx_constraints)
                prob_status = "error"
                try:
                    prob.solve(solver=cp.SCS, verbose=False, max_iters=5000)
                    prob_status = prob.status
                except Exception:
                    pass

                if prob_status in ("optimal", "optimal_inaccurate"):
                    w_arr = np.array(w_var.value).flatten()
                    w_arr = np.where(w_arr < -1e-10, 0.0, w_arr)
                    solver_used = "cvxpy"
                    status = "optimal"
                    try:
                        solve_time = float(prob.solver_stats.solve_time) * 1000
                    except Exception:
                        solve_time = 0.0
                else:
                    # Fallback to scipy
                    scipy_specs = _build_scipy_specs(request.constraints)
                    sr = solvers.solve(
                        np_obj_fn, scipy_specs, n, asset_ids, prefer_cvxpy=False
                    )
                    w_arr = sr.weights
                    solver_used = "scipy"
                    status = sr.status
                    solve_time = sr.solve_time_ms
            else:
                # Force scipy
                scipy_specs = _build_scipy_specs(request.constraints)
                sr = solvers.solve(
                    np_obj_fn, scipy_specs, n, asset_ids, prefer_cvxpy=False
                )
                w_arr = sr.weights
                solver_used = "scipy"
                status = sr.status
                solve_time = sr.solve_time_ms

        # ── Step 2: normalise weights ────────────────────────────────────
        w_arr = np.clip(w_arr, 0.0, 1.0)
        if w_arr.sum() > 1e-9:
            w_arr = w_arr / w_arr.sum()
        weights = pd.Series(w_arr, index=asset_ids)

        # ── Step 3: metrics ───────────────────────────────────────────────
        port_ret = float(w_arr @ mu)
        port_var = float(w_arr @ cov @ w_arr)
        port_std = float(np.sqrt(max(port_var, 0.0)))
        rf = 0.0
        sharpe = (port_ret - rf) / port_std if port_std > 1e-9 else None
        rc = _rc(weights, request.covariance_matrix) if port_std > 1e-9 else None

        # ── Step 4: constraint violations ────────────────────────────────
        violations: dict[str, float] = {}
        for cfg in request.constraints:
            _, check_fn = build_constraint(cfg.type, cfg.params, n, asset_ids)
            violations.update(check_fn(w_arr))

        violation_values = list(violations.values())
        max_violation = max(violation_values) if violation_values else 0.0
        constraints_satisfied = bool(max_violation < 1e-5)

        # ── Step 5: objective value ─────────────────────────────────────
        raw_obj_fn = get_objective(request.objective)
        obj_val = raw_obj_fn(w_arr, mu, cov, lam)

        return OptimizationResult(
            weights=weights,
            objective_value=obj_val,
            solver_status=status,
            solver_used=solver_used,
            solve_time_ms=solve_time,
            portfolio_variance=port_var,
            portfolio_std=port_std,
            expected_return=port_ret,
            sharpe_ratio=sharpe,
            risk_contribution=rc,
            constraints_satisfied=constraints_satisfied,
            constraint_violations={
                k: float(v) for k, v in violations.items() if v > 1e-9
            },
            version_id=request.version_id,
        )
