"""
core.research.portfolio.objectives
==================================
目标函数工厂。
每个目标函数返回可调用对象，供 solver 使用。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_weight_vector(n: int) -> np.ndarray:
    return np.ones(n) / n


def _risk_contributions(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """
    各资产风险贡献 RC_i = w_i * (Σw)_i / √(w'Σw)
    """
    port_risk = np.sqrt(w @ cov @ w)
    if port_risk < 1e-12:
        return np.full_like(w, 0.0)
    marginal_risk = cov @ w
    return w * marginal_risk / port_risk


# ── Objective Registry ─────────────────────────────────────────────────────

OBJECTIVE_REGISTRY: dict[str, dict] = {}


def _register(name: str, needs_mu: bool, needs_lambda: bool, doc: str):
    def decorator(fn):
        OBJECTIVE_REGISTRY[name] = {
            "fn": fn,
            "needs_mu": needs_mu,
            "needs_lambda": needs_lambda,
            "__doc__": doc,
        }
        return fn
    return decorator


# ── 1. min_variance ────────────────────────────────────────────────────────

@_register("min_variance", needs_mu=False, needs_lambda=False,
           doc="min w'Σw")
def min_variance(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, lam: float) -> float:
    return float(w @ cov @ w)


@_register("max_return", needs_mu=True, needs_lambda=False,
           doc="max w'μ")
def max_return(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, lam: float) -> float:
    return float(-w @ mu)  # negate for minimizer


# ── 2. max_sharpe ───────────────────────────────────────────────────────────

@_register("max_sharpe", needs_mu=True, needs_lambda=False,
           doc="max (w'μ) / √(w'Σw)")
def max_sharpe(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, lam: float) -> float:
    port_ret = w @ mu
    port_var = w @ cov @ w
    if port_var < 1e-12:
        return 0.0
    sharpe = port_ret / np.sqrt(port_var)
    return float(-sharpe)  # negate for minimizer


# ── 3. risk_parity ──────────────────────────────────────────────────────────

@_register("risk_parity", needs_mu=False, needs_lambda=False,
           doc="min Σ (RC_i - 1/n)²  where RC_i = w_i*(Σw)_i / σ_p")
def risk_parity(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, lam: float) -> float:
    n = len(w)
    target = 1.0 / n
    rc = _risk_contributions(w, cov)
    return float(np.sum((rc - target) ** 2))


# ── 4. max_utility ─────────────────────────────────────────────────────────

@_register("max_utility", needs_mu=True, needs_lambda=True,
           doc="max w'μ - λ/2 · w'Σw")
def max_utility(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, lam: float) -> float:
    ret = w @ mu
    risk = 0.5 * lam * (w @ cov @ w)
    return float(-(ret - risk))  # negate for minimizer


# ── 5. equal_weight ─────────────────────────────────────────────────────────

@_register("equal_weight", needs_mu=False, needs_lambda=False,
           doc="w_i = 1/n  (no optimization)")
def equal_weight(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, lam: float) -> float:
    # This is a no-op; the optimizer just returns equal weights.
    return 0.0


# ── Public API ─────────────────────────────────────────────────────────────

def get_objective(name: str):
    """返回目标函数，raise KeyError if unknown."""
    if name not in OBJECTIVE_REGISTRY:
        raise KeyError(f"Unknown objective '{name}'. Available: {list(OBJECTIVE_REGISTRY.keys())}")
    return OBJECTIVE_REGISTRY[name]["fn"]


def list_objectives() -> list[str]:
    return list(OBJECTIVE_REGISTRY.keys())


def risk_contribution(weights: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """
    给定权重和协方差矩阵，计算各资产风险贡献 RC_i。
    Σ RC_i = portfolio_std
    """
    w = weights.values.astype(float)
    cov_arr = cov.values.astype(float)
    rc = _risk_contributions(w, cov_arr)
    return pd.Series(rc, index=weights.index)
