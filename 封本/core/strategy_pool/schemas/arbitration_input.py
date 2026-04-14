"""ArbitrationInputBundle — 策略池到 Phase 6 仲裁层的输入接口。

Phase 9 输出 ArbitrationInputBundle（含 StrategyProposal[] + PortfolioProposal）。
Phase 6 正式消费后，产出真正的 ArbitrationDecision[]。
Phase 9 不直接产出 ArbitrationDecision。
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle


class StrategyProposal(BaseModel):
    """单个策略的仲裁候选输入。"""

    proposal_id: str = Field(..., description="提案唯一 ID")
    strategy_id: str = Field(..., description="策略 ID")
    bundles: List[StrategySignalBundle] = Field(
        default_factory=list, description="策略产出的信号包列表"
    )
    aggregate_direction: str = Field(
        "FLAT", description="聚合方向：LONG / SHORT / FLAT"
    )
    aggregate_strength: float = Field(
        0.0, ge=0.0, le=1.0, description="聚合强度"
    )
    aggregate_confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="聚合置信度"
    )
    portfolio_weight: float = Field(
        0.0, ge=0.0, le=1.0, description="在组合中的权重"
    )


class PortfolioProposal(BaseModel):
    """组合级仲裁候选输入（由 MultiStrategyComposer 产出）。"""

    proposal_id: str = Field(..., description="提案唯一 ID")
    portfolio_id: str = Field(..., description="组合 ID")
    proposals: List[StrategyProposal] = Field(
        default_factory=list, description="各策略的提案列表"
    )
    composite_direction: str = Field(
        "FLAT", description="组合聚合方向"
    )
    composite_strength: float = Field(
        0.0, ge=0.0, le=1.0, description="组合聚合强度"
    )
    composite_confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="组合聚合置信度"
    )
    weight_method: str = Field(
        "equal",
        description="权重分配方法：equal / ir / risk_parity / manual",
    )


class ArbitrationInputBundle(BaseModel):
    """
    交付给 Phase 6 的仲裁输入包。

    Phase 6 消费此对象后，产出真正的 ArbitrationDecision[]。
    """

    bundle_id: str = Field(..., description="输入包唯一 ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="生成时间"
    )
    portfolio_proposal: PortfolioProposal = Field(
        ..., description="组合级提案"
    )
    supporting_factor_ids: List[str] = Field(
        default_factory=list,
        description="Phase 4 因子 ID 引用列表",
    )
    regime_context: Optional[Dict] = Field(
        None, description="Phase 5 宏观状态引用"
    )
