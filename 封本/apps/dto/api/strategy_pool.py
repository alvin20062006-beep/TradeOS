"""
apps/dto/api/strategy_pool.py — 策略池 API DTO

约束：
- 全部 DTO，不引用核心 StrategySignalBundle / PortfolioProposal 等
- AI 通过 DTO 提交策略信号，不直接绑定核心对象
- /strategy-pool/propose 返回 DecisionBundle（包装 DecisionResponse）
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── 请求 ────────────────────────────────────────────────────

class StrategySignalBundleDTO(BaseModel):
    """策略信号包（API DTO，不引用核心 StrategySignalBundle）。"""

    bundle_id: str = Field(description="信号包 ID")
    source_strategy_id: str = Field(description="来源策略 ID")
    symbol: str = Field(description="标的代码")
    direction: Literal["LONG", "SHORT", "FLAT"] = Field(description="信号方向")
    strength: float = Field(0.0, ge=0.0, le=1.0)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    timestamp: Optional[datetime] = None
    supporting_signals: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class StrategyProposalDTO(BaseModel):
    """策略提案（API DTO）。"""

    proposal_id: str
    strategy_id: str
    bundles: list[StrategySignalBundleDTO] = Field(default_factory=list)
    aggregate_direction: Literal["LONG", "SHORT", "FLAT"] = Field(default="FLAT")
    aggregate_strength: float = Field(0.0, ge=0.0, le=1.0)
    aggregate_confidence: float = Field(0.0, ge=0.0, le=1.0)
    portfolio_weight: float = Field(1.0, ge=0.0, le=1.0)


class StrategyPoolProposeRequest(BaseModel):
    """
    POST /strategy-pool/propose 请求。

    接收 StrategySignalBundle[]，通过 MultiStrategyComposer 聚合，
    再通过 ArbitrationEngine.arbitrate_portfolio() 产出决策。
    """

    portfolio_id: str = Field(description="组合 ID")
    symbol: str = Field(description="标的代码")
    proposals: list[StrategyProposalDTO] = Field(
        min_length=1,
        description="至少一个策略提案",
    )
    weight_method: Literal["equal", "ir", "risk_parity", "manual"] = Field(
        default="equal"
    )
    timestamp: Optional[datetime] = None


# ── 响应 ────────────────────────────────────────────────────

class StrategySignalBundleView(BaseModel):
    """StrategySignalBundle 展示模型。"""

    bundle_id: str
    source_strategy_id: str
    symbol: str
    direction: str
    strength: float
    confidence: float


class StrategyProposalView(BaseModel):
    """策略提案展示模型。"""

    proposal_id: str
    strategy_id: str
    bundles: list[StrategySignalBundleView] = Field(default_factory=list)
    aggregate_direction: str
    aggregate_strength: float
    aggregate_confidence: float
    portfolio_weight: float


class StrategyPoolDecisionBundle(BaseModel):
    """
    策略池仲裁结果包（包装 Phase 6 ArbitrationDecision）。

    与核心 ArbitrationDecision 完全解耦。
    AI 只通过此 DTO 接收策略池仲裁结果。
    """

    ok: bool = True
    decision_id: str
    symbol: str
    bias: str
    confidence: float
    signal_count: int
    rules_applied: list[str] = Field(default_factory=list)
    timestamp: datetime
    arbitration_latency_ms: float
    source: str = "strategy_pool"
    portfolio_id: str
    proposals: list[StrategyProposalView] = Field(default_factory=list)
    composite_direction: str
    composite_strength: float


class StrategyPoolProposeResponse(BaseModel):
    """POST /strategy-pool/propose 响应。"""

    ok: bool = True
    task_id: str = Field(description="任务 ID（首批：同步处理，task_id=immediate）")
    status: Literal["done", "pending", "error"] = "done"
    message: str = ""
    decision: Optional[StrategyPoolDecisionBundle] = None
