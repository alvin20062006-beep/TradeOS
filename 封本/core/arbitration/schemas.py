"""
Arbitration Schemas
==================

Phase 6 仲裁层专用的数据结构。
继承 core.schemas 中已定义的 ArbitrationDecision。

关键设计原则：
- 五大投票信号（technical/chan/orderflow/sentiment/macro）有 Optional 包装
- 基本盘作为低频背景约束，不参与投票
- 字段默认值统一用 Field(default_factory=list)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from core.analysis.fundamental.report import FundamentalReport
from core.schemas import (
    ChanSignal,
    Direction,
    MacroSignal,
    OrderFlowSignal,
    Regime,
    SentimentEvent,
    TechnicalSignal,
)

# ─────────────────────────────────────────────────────────────
# Input Schemas
# ─────────────────────────────────────────────────────────────


class DirectionalSignal(BaseModel):
    """
    方向信号的标准化包装。

    所有引擎信号都会被归一化为此格式，再送入仲裁投票。
    统一字段名，避免不同引擎 schema 不一致的问题。
    """
    engine_name: str
    direction: Direction
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    regime: Optional[Regime] = None
    weight: float = 1.0
    raw_signal: Optional[BaseModel] = None

    def score(self) -> float:
        """加权得分（-1 到 +1）。"""
        d = 1 if self.direction.value == "long" else -1
        return d * self.confidence * self.weight


class SignalBundle(BaseModel):
    """
    收集到的信号包。

    由 SignalCollector 汇总六大分析模块的输出，
    统一时间戳后送入仲裁引擎。
    """
    timestamp: datetime
    symbol: str

    # ── 五大投票信号 ──────────────────────────────────────
    technical: Optional[TechnicalSignal] = None
    chan: Optional[ChanSignal] = None
    orderflow: Optional[OrderFlowSignal] = None
    sentiment: Optional[SentimentEvent] = None
    macro: Optional[MacroSignal] = None

    # ── 基本盘参考（背景约束，不参与投票） ────────────────
    fundamental: Optional[FundamentalReport] = None

    # ── 元数据 ───────────────────────────────────────────
    collection_latency_ms: float = 0.0

    @property
    def signals_present(self) -> int:
        """实际收到的信号数量（不含基本盘）。"""
        return sum(
            1
            for s in [
                self.technical,
                self.chan,
                self.orderflow,
                self.sentiment,
                self.macro,
            ]
            if s is not None
        )


# ─────────────────────────────────────────────────────────────
# Reasoning / Audit Schemas
# ─────────────────────────────────────────────────────────────


class DecisionRationale(BaseModel):
    """
    决策理由链中的单个条目。

    记录每个信号的原始置信度、权重和加权贡献，
    供审计和可解释性使用。
    """
    signal_name: str = Field(..., description="信号来源：technical/chan/orderflow/sentiment/macro")
    direction: Direction = Field(..., description="信号方向")
    confidence: float = Field(..., ge=0.0, le=1.0, description="原始置信度")
    weight: float = Field(..., ge=0.0, description="应用权重（含规则调整）")
    contribution: float = Field(..., description="加权贡献（归一化前可超 ±1.0）")
    rule_adjustments: List[str] = Field(
        default_factory=list,
        description="触发此信号的规则调整记录",
    )


class ConflictRecord(BaseModel):
    """
    单次方向冲突记录。
    """
    signal_a: str = Field(..., description="冲突信号 A 名称")
    signal_b: str = Field(..., description="冲突信号 B 名称")
    direction_a: Direction = Field(..., description="A 的方向")
    direction_b: Direction = Field(..., description="B 的方向")
    resolution: str = Field(..., description="解决方式描述")
    rule_applied: str = Field(..., description="应用的仲裁规则名称")


# ─────────────────────────────────────────────────────────────
# Output Schema
# ─────────────────────────────────────────────────────────────

# 六种仲裁层动作（收紧版，不含 execution 层语义）
ARBITRATION_BIAS_OPTIONS = [
    "no_trade",
    "long_bias",
    "short_bias",
    "hold_bias",
    "reduce_risk",
    "exit_bias",
]


class ArbitrationDecision(BaseModel):
    """
    仲裁层最终决策。

    继承 core.schemas.ArbitrationDecision 的执行相关字段，
    新增 Phase 6 仲裁层专有字段。

    与 core.schemas.ArbitrationDecision 的字段兼容，
    同时补充：bias、评分明细、理由链、冲突记录、约束条件。
    """
    # ── 标识 ─────────────────────────────────────────────
    decision_id: str = Field(..., description="唯一决策 ID（UUID）")
    timestamp: datetime = Field(..., description="决策时间（UTC）")
    symbol: str = Field(..., description="标的代码")

    # ── 仲裁层核心输出 ───────────────────────────────────
    bias: str = Field(
        ...,
        description="仲裁层动作：no_trade/long_bias/short_bias/hold_bias/reduce_risk/exit_bias",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)

    # 评分明细
    long_score: float = Field(0.0, description="做多加权得分（0-1）")
    short_score: float = Field(0.0, description="做空加权得分（0-1）")
    neutrality_score: float = Field(0.0, description="中性得分（0-1）")

    # 理由链与冲突
    rationale: List[DecisionRationale] = Field(
        default_factory=list,
        description="决策理由链",
    )
    conflicts: List[ConflictRecord] = Field(
        default_factory=list,
        description="检测到的方向冲突",
    )

    # 基本盘约束
    fundamental_reference: Optional[str] = Field(
        None,
        description="基本盘评级：A/B/C/D",
    )
    fundamental_veto_triggered: bool = Field(
        False,
        description="是否触发基本盘 veto（D 级）",
    )

    # 宏观约束
    macro_regime: Optional[str] = Field(
        None,
        description="宏观风险偏好：risk_on/risk_off/mixed",
    )
    risk_adjustment: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="风险调整系数（0=完全回避，1=正常敞口）",
    )

    # 审计元数据
    rules_applied: List[str] = Field(
        default_factory=list,
        description="本次决策应用的仲裁规则",
    )
    signal_count: int = Field(0, description="参与仲裁的信号数量")
    arbitration_latency_ms: float = Field(
        0.0,
        description="仲裁耗时（毫秒）",
    )


# ─────────────────────────────────────────────────────────────
# Internal Types
# ─────────────────────────────────────────────────────────────


class SignalScore(BaseModel):
    """单个信号的评分结果。"""
    engine_name: str
    direction: Direction
    raw_confidence: float
    adjusted_confidence: float
    weight: float
    contribution: float
    regime: Optional[Regime] = None
    rule_adjustments: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Phase 9 → Phase 6 Bridge Types
# ─────────────────────────────────────────────────────────────

class _StrategySignalSource(BaseModel):
    """
    Phase 9 → Phase 6 桥接输入对象。

    仅服务于 arbitrate_portfolio()，不参与 arbitrate()。
    不属于 Phase 6 核心 schema 层级，仅为内部转换对象。

    语义：
    - 将 Phase 9 的多策略聚合提案（StrategyProposal）
      映射为 Phase 6 的 DirectionalSignal 格式。
    - engine_name 前缀为 "strategy_pool:"，与原有 5 类信号平级参与仲裁，
      但语义不同（已聚合的策略决策 vs 原始市场分析）。
    """
    proposal_id: str
    strategy_id: str
    aggregate_direction: str  # "LONG" | "SHORT" | "FLAT"
    aggregate_strength: float = Field(0.0, ge=0.0, le=1.0)
    aggregate_confidence: float = Field(0.0, ge=0.0, le=1.0)
    portfolio_weight: float = Field(0.0, ge=0.0, le=1.0)

    def to_directional(self) -> DirectionalSignal:
        """
        转换为 DirectionalSignal，送入 Phase 6 现有规则链。

        engine_name = "strategy_pool:{strategy_id}"，
        参与现有 5 规则链（FundamentalVeto / MacroAdjustment / DirectionConflict /
        ConfidenceWeight / RegimeFilter），其中前两条 universal 规则可覆盖本信号。
        """
        dir_map = {
            "LONG": Direction.LONG,
            "SHORT": Direction.SHORT,
            "FLAT": Direction.FLAT,
        }
        # 未知方向默认 FLAT
        direction = dir_map.get(self.aggregate_direction.upper(), Direction.FLAT)

        return DirectionalSignal(
            engine_name=f"strategy_pool:{self.strategy_id}",
            direction=direction,
            confidence=self.aggregate_confidence,
            weight=self.portfolio_weight if self.portfolio_weight > 0 else 1.0,
            regime=None,
        )
