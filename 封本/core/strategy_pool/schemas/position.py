"""StrategyPosition — 策略级持仓快照。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StrategyPosition(BaseModel):
    """
    策略级持仓快照。

    记录单个策略对单个标的的持仓状态，供组合器汇总。
    """

    strategy_id: str = Field(..., description="策略 ID")
    symbol: str = Field(..., description="标的代码")
    direction: str = Field("FLAT", description="持仓方向：LONG / SHORT / FLAT")
    qty: float = Field(0.0, ge=0.0, description="持仓数量")
    entry_price: Optional[float] = Field(None, description="入场价")
    current_price: Optional[float] = Field(None, description="当前价")
    unrealized_pnl: Optional[float] = Field(None, description="未实现盈亏")
    unrealized_pnl_pct: Optional[float] = Field(None, description="未实现盈亏 %")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="更新时间"
    )
