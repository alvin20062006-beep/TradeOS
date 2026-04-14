"""
apps/dto/api/arbitration.py — 仲裁层 API DTO

API 层接收 DTO，内部转换为核心对象后调用 ArbitrationEngine。
AI 只能通过这些 DTO 与仲裁层交互，禁止直接绑定 ArbitrationDecision。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── 请求 ────────────────────────────────────────────────────

class ArbitrationRunRequest(BaseModel):
    """
    POST /arbitration/run 请求（旧入口：消费 Phase 5 信号）。

    字段设计：
    - 最小可用：symbol + direction + confidence（走通主链路）
    - 扩展字段：regime / regime_confidence（影响 RegimeFilterRule）
    - 扩展字段：fundamental_score（影响 FundamentalVetoRule）
    """

    symbol: str = Field(min_length=1, max_length=16)
    direction: Literal["LONG", "SHORT", "FLAT"] = Field(description="信号方向")
    confidence: float = Field(ge=0.0, le=1.0, description="信号置信度")
    strength: float = Field(default=0.5, ge=0.0, le=1.0)

    # 扩展字段（可选，影响规则链）
    regime: Literal["trending_up", "trending_down", "ranging", "volatile", "unknown"] = (
        Field(default="trending_up")
    )
    regime_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    fundamental_score: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="基本面评分，影响 FundamentalVetoRule",
    )
    orderflow_score: float = Field(default=0.5, ge=0.0, le=1.0)
    sentiment_score: float = Field(default=0.5, ge=0.0, le=1.0)
    macro_score: float = Field(default=0.5, ge=0.0, le=1.0)

    timestamp: Optional[datetime] = Field(default=None, description="时间戳，默认当前时间")


class PortfolioArbitrationRequest(BaseModel):
    """
    POST /arbitration/run-portfolio 请求（新入口：消费 Phase 9 策略池）。

    策略信号作为请求体传入，不引用核心 StrategySignalBundle 类型。
    """

    portfolio_id: str = Field(description="组合 ID，如 AAPL-SP")
    symbol: str = Field(description="标的代码，如 AAPL")

    # 策略提案（可多个，模拟 Phase 9 输出）
    proposals: list["StrategyProposalRequest"] = Field(
        min_length=1, description="至少一个策略提案"
    )

    timestamp: Optional[datetime] = Field(default=None)

    @field_validator("portfolio_id")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class StrategyProposalRequest(BaseModel):
    """策略提案（嵌入 DTO，不引用核心 StrategySignalBundle）。"""

    proposal_id: str
    strategy_id: str = Field(description="策略标识，如 trend / mean_reversion")
    aggregate_direction: Literal["LONG", "SHORT", "FLAT"]
    aggregate_strength: float = Field(ge=0.0, le=1.0)
    aggregate_confidence: float = Field(ge=0.0, le=1.0)
    portfolio_weight: float = Field(default=1.0, ge=0.0, le=1.0)

    # 可选：bundle 列表（模拟 StrategySignalBundle 输出）
    bundle_count: int = Field(default=1, ge=1, description="bundle 数量")


# ── 响应 ────────────────────────────────────────────────────

class DecisionRationaleView(BaseModel):
    """决策理由（展示用 view model）。"""

    signal_name: str
    direction: str
    confidence: float
    weight: float
    contribution: float
    rule_adjustments: list[str] = Field(default_factory=list)


class ArbitrationResponse(BaseModel):
    """
    仲裁决策响应（与核心 ArbitrationDecision 完全解耦）。

    AI 通过此 DTO 接收结果，禁止直接访问 ArbitrationDecision 对象。
    """

    ok: bool = True
    decision_id: str = Field(description="决策 ID")
    symbol: str
    bias: str = Field(description="long_bias | short_bias | hold_bias | no_trade")
    confidence: float = Field(ge=0.0, le=1.0)
    signal_count: int = Field(ge=0, description="参与评分的信号数量")
    rules_applied: list[str] = Field(
        default_factory=list,
        description="应用的规则名称列表",
    )
    rationale: list[DecisionRationaleView] = Field(
        default_factory=list,
        description="各信号理由",
    )
    timestamp: datetime
    arbitration_latency_ms: float = Field(ge=0.0)
    source: str = Field(
        default="arbitration",
        description="来源：arbitration（旧入口）| portfolio（策略池入口）",
    )

    model_config = {"str_strip_whitespace": True}


# 修复 forward reference
PortfolioArbitrationRequest.model_rebuild()
