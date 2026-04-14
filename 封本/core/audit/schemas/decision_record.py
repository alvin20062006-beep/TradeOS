"""DecisionRecord — Phase 6 仲裁决策审计记录。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from core.audit.schemas.audit_record import AuditRecord
from core.schemas import Direction


class SignalSnapshot(BaseModel):
    """
    Phase 6 EngineSignal 的审计快照。

    保留原始信号的核心字段，避免 Phase 8 强耦合 Phase 6 原生对象。
    仅保留审计和复盘所需的最小字段集。
    """

    source_module: str = Field(
        ..., description="信号来源模块：technical / fundamental / chan / macro / sentiment / orderflow"
    )
    signal_type: str = Field(..., description="信号类型：trend_up / breakout / mean_reversion 等")
    direction: str = Field(..., description="信号方向：LONG / SHORT / NEUTRAL")
    confidence: float = Field(..., ge=0, le=1, description="信号置信度")
    regime: Optional[str] = Field(None, description="检测到的市场状态")
    score: Optional[float] = Field(None, description="信号评分（0-1）")
    metadata: dict = Field(
        default_factory=dict,
        description="附加元数据（可扩展，不强耦合结构）",
    )

    @classmethod
    def from_signal(cls, signal) -> SignalSnapshot:
        """从 Phase 6 EngineSignal 快照化。"""
        return cls(
            source_module=signal.get("source_module", signal.get("module", "unknown")),
            signal_type=signal.get("signal_type", signal.get("type", "unknown")),
            direction=signal.get("direction", "NEUTRAL"),
            confidence=signal.get("confidence", 0.0),
            regime=signal.get("regime"),
            score=signal.get("score"),
            metadata=signal.get("metadata", {}),
        )


class DecisionRecord(AuditRecord):
    """
    仲裁决策审计记录（Phase 6 → Phase 8）。

    记录从信号输入到仲裁输出的完整链路，用于事后复盘和 feedback 生成。
    执行结果（realized_pnl 等）事后追加，不修改原记录。
    """

    source_phase: Literal["Phase 6"] = "Phase 6"

    # ── 仲裁输入快照 ────────────────────────────────
    input_signals: List[SignalSnapshot] = Field(
        default_factory=list,
        description="各 engine 原始信号快照（SignalSnapshot[]）",
    )

    # ── 仲裁参数 ────────────────────────────────────
    final_confidence: float = Field(0.0, ge=0, le=1)
    bias: str = Field(
        ..., description="仲裁输出 bias：long_bias / short_bias / exit_bias / reduce_risk / hold / no_trade"
    )

    # ── 仲裁输出 ────────────────────────────────────
    target_direction: str = Field(..., description="目标持仓方向")
    target_quantity: float = Field(0.0, ge=0, description="目标数量")
    stop_price: Optional[float] = Field(None, description="止损价")
    arbitration_confidence: float = Field(0.0, ge=0, le=1)
    no_trade_reason: Optional[str] = Field(None)

    # ── 执行关联 ────────────────────────────────────
    execution_record_id: Optional[str] = Field(
        None, description="关联的 ExecutionRecord ID（事后追加）"
    )

    # ── 事后评估字段（平仓后追加，不修改原记录） ──────────
    realized_pnl_pct: Optional[float] = Field(
        None, description="事后平仓收益（%，开仓→平仓完整闭环后填入）"
    )
    signal_age_hours: Optional[float] = Field(
        None, description="信号从生成到开仓的时长（小时）"
    )
    holding_period_hours: Optional[float] = Field(
        None, description="持仓时长（开仓→平仓，小时）"
    )
    entry_price: Optional[float] = Field(None)
    exit_price: Optional[float] = Field(None)

    # ── 标记 ───────────────────────────────────────
    correction_of: Optional[str] = Field(
        None, description="如果此记录是对某 audit_id 的修正，填原 ID"
    )
