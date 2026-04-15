"""StrategySignalBundle — 策略层统一打包对象。

仅负责将策略输出打包为统一格式，供组合器和仲裁接口消费。
不自建信号生成逻辑，复用已有模块的输出。
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class StrategySignalBundle(BaseModel):
    """
    策略层统一打包对象。

    不是底层信号系统，而是策略输出的标准化包装。
    supporting_signals / supporting_snapshots 仅持有 ID 引用，不持有原生对象。
    """

    bundle_id: str = Field(..., description="信号包唯一 ID")
    source_strategy_id: str = Field(..., description="来源策略 ID")
    symbol: str = Field(..., description="标的代码")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="信号生成时间"
    )
    direction: Literal["LONG", "SHORT", "FLAT"] = Field(
        ..., description="信号方向"
    )
    strength: float = Field(0.0, ge=0.0, le=1.0, description="信号强度 0-1")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="置信度 0-1")

    # ── 支撑信号引用 ─────────────────────────────
    supporting_signals: List[str] = Field(
        default_factory=list,
        description="支撑信号 ID 列表（来自其他模块，仅 ID 引用）",
    )
    supporting_snapshots: List[str] = Field(
        default_factory=list,
        description="因子快照 ID 列表（Phase 4 因子 ID 引用）",
    )

    # ── 扩展 ────────────────────────────────────
    metadata: Dict = Field(
        default_factory=dict, description="可扩展元数据"
    )
