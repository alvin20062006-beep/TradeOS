"""StrategySpec — 策略元信息与状态枚举。"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class StrategyStatus(str, Enum):
    """策略生命周期状态。"""
    CANDIDATE = "candidate"      # 待评估
    ACTIVE = "active"            # 启用
    INACTIVE = "inactive"        # 停用（可重新激活）
    DEPRECATED = "deprecated"    # 下架（永久）


class StrategyType(str, Enum):
    """策略类型枚举。"""
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"


class StrategySpec(BaseModel):
    """
    策略规格定义。

    描述一个策略的全部元信息，包括类型、参数、风控约束、生命周期状态。
    append-only 注册表持有此对象的序列化副本。
    """

    strategy_id: str = Field(..., description="策略唯一 ID（UUID）")
    name: str = Field(..., description="策略名称（如 trend_ma20_aapl）")
    strategy_type: StrategyType = Field(..., description="策略类型")
    bias: str = Field(
        "market_neutral",
        description="策略偏向：long_bias / short_bias / market_neutral",
    )
    direction: Literal["LONG", "SHORT", "BOTH"] = Field(
        "BOTH", description="允许的方向"
    )
    params: Dict = Field(
        default_factory=dict,
        description="策略参数（lookback / threshold / ma_period 等）",
    )
    lookback: int = Field(20, ge=1, description="回看窗口（天数）")
    max_position_pct: float = Field(
        0.1, ge=0.0, le=1.0, description="最大仓位占比（0-1）"
    )
    stop_loss_pct: float = Field(
        0.02, ge=0.0, le=1.0, description="止损比例"
    )
    target_return_pct: float = Field(
        0.05, ge=0.0, description="目标收益率"
    )
    risk_limits: Dict = Field(
        default_factory=dict,
        description="策略级风控参数（由 Phase 7 RiskLimits 约束）",
    )
    description: str = Field("", description="策略描述")
    version: int = Field(1, ge=1, description="策略版本号")

    # ── 生命周期字段 ──────────────────────────────
    status: StrategyStatus = Field(
        StrategyStatus.CANDIDATE, description="策略状态"
    )
    registered_at: datetime = Field(
        default_factory=datetime.utcnow, description="注册时间"
    )
    activated_at: Optional[datetime] = Field(
        None, description="激活时间"
    )
    deactivated_at: Optional[datetime] = Field(
        None, description="停用时间"
    )
    deprecation_reason: Optional[str] = Field(
        None, description="下架原因"
    )
