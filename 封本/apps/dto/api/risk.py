"""
apps/dto/api/risk.py — 风控引擎 API DTO
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from apps.dto.api.audit import LimitCheckView


# ── 请求 ────────────────────────────────────────────────────

class RiskCalculateRequest(BaseModel):
    """POST /risk/calculate 请求。"""

    # 仲裁决策摘要（API 层做最小转换，不引用核心 ArbitrationDecision）
    decision_id: str
    symbol: str
    bias: Literal["long_bias", "short_bias", "hold_bias", "no_trade"]
    confidence: float = Field(ge=0.0, le=1.0)

    # 组合状态
    # 组合状态
    portfolio_value: float = Field(gt=0, description="组合总市值")
    current_price: float = Field(gt=0, description="当前价格")
    regime: Literal["trending_up", "trending_down", "ranging", "volatile", "unknown"] = (
        Field(default="trending_up")
    )
    existing_position: float = Field(default=0.0, description="现有持仓数量")
    existing_direction: Literal["LONG", "SHORT", "FLAT"] = Field(
        default="FLAT", description="现有持仓方向"
    )
    avg_entry_price: float = Field(default=0.0, ge=0, description="平均入场价")

    # 风控参数（可选，优先使用系统默认值）
    max_position_pct: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="最大仓位占比（None=系统默认值）",
    )
    regime: Literal["trending_up", "trending_down", "ranging", "volatile", "unknown"] = (
        Field(default="trending_up")
    )

    timestamp: Optional[datetime] = Field(default=None)


class ExecutionPlanView(BaseModel):
    """执行计划（展示用 view model）。"""

    algorithm: str = Field(description="执行算法名称")
    limit_price: Optional[float] = Field(default=None, description="限价（None=市价）")
    stop_price: Optional[float] = Field(default=None, description="止损价")
    timestamp: datetime


# ── 响应 ────────────────────────────────────────────────────

class PositionPlanView(BaseModel):
    """
    仓位计划响应（与核心 PositionPlan 完全解耦）。

    AI 通过此 DTO 接收结果，禁止直接访问 PositionPlan 对象。
    """

    ok: bool = True
    plan_id: str
    symbol: str
    direction: str = Field(description="目标剩余暴露方向 LONG | SHORT | FLAT")
    exec_action: str = Field(description="BUY | SELL | FLAT")
    final_quantity: float = Field(description="最终交易数量（可为 0）")
    veto_triggered: bool = Field(description="是否被 veto")
    limit_checks: list[LimitCheckView] = Field(default_factory=list)
    execution_plan: Optional["ExecutionPlanView"] = Field(
        default=None, description="执行计划（veto=False 时有值）"
    )
    timestamp: datetime


# 修复 forward reference
PositionPlanView.model_rebuild()
