"""
core.research.portfolio.schema
==============================
Pydantic schemas for portfolio optimization.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Constraint Config ──────────────────────────────────────────────────────

class ConstraintConfig(BaseModel):
    """
    单个约束配置。

    通用 params 约定（按 type）：
    ───────────────────────────────────────────────────────────────────────
    type                      params 约定
    ───────────────────────────────────────────────────────────────────────
    sum_to_one                {}  （无参数）
    long_only                 {}  （无参数）
    max_weight                {"limit": float}  # w_i ≤ limit
    min_weight                {"limit": float}  # w_i ≥ limit
    sector_target_exposure    {
        "sector_map": dict[str, str],   # asset_id → sector
        "targets": dict[str, float],    # sector → target_weight
    }
    sector_deviation_limit     {
        "sector_map": dict[str, str],                # asset_id → sector
        "benchmark_sector_weights": dict[str, float], # sector → benchmark_weight
        "max_deviation": float                       # |w_sector - b_sector| ≤ δ
    }
    max_turnover              {
        "current_weights": dict[str, float],  # asset_id → w_prev
        "limit": float                         # Σ|w_i - w_i_prev| ≤ limit
    }
    max_leverage               {"limit": float}  # Σ|w_i| ≤ limit
    tracking_error             {
        "benchmark_weights": dict[str, float], # asset_id → b_i
        "covariance_matrix": list[list[float]],  # Σ (Python list, cvxpy/scipy 接受 numpy 或 list)
                                注意：传入时使用 list[list[float]]，内部自动转为 np.ndarray
        "limit": float                          # √((w-b)'Σ(w-b)) ≤ limit
    }
    ───────────────────────────────────────────────────────────────────────
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    type: str = Field(..., description="约束类型 ID")
    params: dict = Field(default_factory=dict, description="约束参数")


# ── Optimization Request ───────────────────────────────────────────────────

class OptimizationRequest(BaseModel):
    """组合优化请求。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # 必需
    expected_returns: pd.Series = Field(
        ..., description="预期收益 μ，index = asset_id"
    )
    covariance_matrix: pd.DataFrame = Field(
        ..., description="协方差矩阵 Σ，index/columns = asset_id"
    )

    # 目标
    objective: str = Field(
        default="min_variance",
        description="目标函数 ID：max_sharpe / min_variance / risk_parity / max_utility / max_return",
    )
    risk_aversion: float = Field(
        default=1.0, ge=0.0, description="风险厌恶系数 λ（用于 max_utility）"
    )

    # 约束
    constraints: list[ConstraintConfig] = Field(
        default_factory=lambda: [
            ConstraintConfig(type="sum_to_one"),
            ConstraintConfig(type="long_only"),
        ],
        description="约束条件列表",
    )

    # 可选
    current_weights: pd.Series | None = Field(
        default=None, description="当前权重（用于换手约束）"
    )
    benchmark_weights: pd.Series | None = Field(
        default=None, description="基准权重（用于跟踪误差 / 行业偏离）"
    )
    sector_map: dict[str, str] | None = Field(
        default=None, description="asset_id → sector"
    )

    version_id: str = Field(
        default="", description="关联的研究版本 ID"
    )

    # ── Validators ───────────────────────────────────────────────────────

    @field_validator("expected_returns", mode="before")
    @classmethod
    def _coerce_returns(cls, v):
        if isinstance(v, pd.Series):
            return v
        if isinstance(v, dict):
            return pd.Series(v)
        raise TypeError("expected_returns must be a pandas Series or dict")

    @field_validator("covariance_matrix", mode="before")
    @classmethod
    def _coerce_cov(cls, v):
        if isinstance(v, pd.DataFrame):
            return v
        if isinstance(v, (list, np.ndarray)):
            return pd.DataFrame(v)
        raise TypeError("covariance_matrix must be a pandas DataFrame or array")

    @field_validator("current_weights", "benchmark_weights", mode="before")
    @classmethod
    def _coerce_series(cls, v):
        if v is None:
            return None
        if isinstance(v, pd.Series):
            return v
        if isinstance(v, dict):
            return pd.Series(v)
        raise TypeError("current_weights / benchmark_weights must be Series, dict, or None")

    @model_validator(mode="after")
    def _validate_asset_consistency(self) -> "OptimizationRequest":
        """资产集合一致性校验。"""
        assets_mu = set(self.expected_returns.index)
        assets_cov = set(self.covariance_matrix.index)
        if assets_mu != assets_cov:
            raise ValueError(
                f"expected_returns index {sorted(assets_mu)} != "
                f"covariance_matrix index {sorted(assets_cov)}"
            )
        n = self.covariance_matrix.shape[0]
        if self.covariance_matrix.shape != (n, n):
            raise ValueError(
                f"covariance_matrix must be square, got shape {self.covariance_matrix.shape}"
            )
        # Symmetry check
        diff = np.abs(self.covariance_matrix.values - self.covariance_matrix.values.T).max()
        if diff > 1e-9:
            raise ValueError("covariance_matrix must be symmetric")
        # PD check
        eigvals = np.linalg.eigvalsh(self.covariance_matrix.values)
        if eigvals.min() < -1e-8:
            raise ValueError("covariance_matrix must be positive semi-definite")

        for name, series in [("current_weights", self.current_weights), ("benchmark_weights", self.benchmark_weights)]:
            if series is not None:
                series_assets = set(series.index)
                if series_assets != assets_mu:
                    raise ValueError(
                        f"{name} index {sorted(series_assets)} must exactly match "
                        f"asset set {sorted(assets_mu)}"
                    )
        return self

    @model_validator(mode="after")
    def _validate_empty_single_asset(self) -> "OptimizationRequest":
        """空输入和单资产行为明确化。"""
        n = len(self.expected_returns)
        if n == 0:
            raise ValueError("expected_returns is empty (no assets)")
        return self


# ── Optimization Result ────────────────────────────────────────────────────

class OptimizationResult(BaseModel):
    """组合优化结果（研究层）。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # 核心
    weights: pd.Series = Field(..., description="优化后权重，index = asset_id")
    objective_value: float = Field(..., description="目标函数值")

    # 求解状态
    solver_status: str = Field(
        ...,
        description="optimal / infeasible / unbounded / max_iter_reached / error",
    )
    solver_used: str = Field(..., description="cvxpy / scipy")
    solve_time_ms: float = Field(..., ge=0.0)

    # 风险/收益指标
    portfolio_variance: float = Field(..., ge=0.0, description="w'Σw")
    portfolio_std: float = Field(..., ge=0.0, description="√(w'Σw)")
    expected_return: float = Field(..., description="w'μ")
    sharpe_ratio: float | None = Field(default=None)
    risk_contribution: pd.Series | None = Field(
        default=None,
        description="各资产风险贡献 RC_i，Σ RC_i = portfolio_std"
    )

    # 约束验证
    constraints_satisfied: bool = Field(...)
    constraint_violations: dict[str, float] = Field(default_factory=dict)

    # 版本
    version_id: str = Field(default="", description="关联的研究版本 ID")

    @field_validator("weights", mode="before")
    @classmethod
    def _coerce_weights(cls, v):
        if isinstance(v, pd.Series):
            return v
        if isinstance(v, dict):
            return pd.Series(v)
        raise TypeError("weights must be a pandas Series")

    @field_validator("risk_contribution", mode="before")
    @classmethod
    def _coerce_rc(cls, v):
        if v is None:
            return None
        if isinstance(v, pd.Series):
            return v
        if isinstance(v, dict):
            return pd.Series(v)
        raise TypeError("risk_contribution must be a pandas Series or None")
