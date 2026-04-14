"""StrategyPortfolio — 策略组合配置。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field

from core.strategy_pool.schemas.strategy import StrategyStatus


class StrategyWeight(BaseModel):
    """单个策略在组合中的权重配置。"""

    strategy_id: str = Field(..., description="策略 ID")
    weight: float = Field(0.0, ge=0.0, le=1.0, description="权重 0-1")
    weight_method: str = Field(
        "equal",
        description="权重分配方法：equal / ir / risk_parity / manual",
    )


class StrategyPortfolio(BaseModel):
    """
    策略组合配置。

    管理多个策略的权重分配、再平衡频率和组合偏向。
    """

    portfolio_id: str = Field(..., description="组合唯一 ID")
    name: str = Field(..., description="组合名称")
    strategy_weights: List[StrategyWeight] = Field(
        default_factory=list, description="策略权重列表"
    )
    rebalance_frequency: str = Field(
        "daily",
        description="再平衡频率：daily / weekly / on_signal",
    )
    portfolio_bias: str = Field(
        "market_neutral",
        description="组合偏向：LONG / SHORT / MARKET_NEUTRAL",
    )
    status: StrategyStatus = Field(
        StrategyStatus.CANDIDATE, description="组合状态"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="创建时间"
    )
    description: str = Field("", description="组合描述")
