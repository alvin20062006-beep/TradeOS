"""ExecutionRecord — Phase 3 执行成交审计记录。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from core.audit.schemas.audit_record import AuditRecord
from core.schemas import ExecutionQuality


class FillSnapshot(BaseModel):
    """
    Phase 3 Fill 对象的审计快照。

    仅保留审计和执行质量评估所需字段，避免 Phase 8 强耦合 Phase 3 原生对象。
    """

    slice_id: str = Field(..., description="分片 ID")
    filled_qty: float = Field(..., ge=0, description="成交数量")
    fill_price: float = Field(..., gt=0, description="成交价")
    fill_time: datetime = Field(..., description="成交时间")
    slippage_bps: float = Field(0.0, description="相对 arrival_price 的滑点（bps）")
    is_leaving_qty: bool = Field(False, description="是否遗留未成交数量")

    @classmethod
    def from_fill(cls, fill) -> FillSnapshot:
        """从 Phase 3 Fill 对象快照化。"""
        return cls(
            slice_id=fill.get("slice_id", fill.get("id", "")),
            filled_qty=fill.get("filled_qty", fill.get("quantity", 0.0)),
            fill_price=fill.get("fill_price", fill.get("price", 0.0)),
            fill_time=fill.get(
                "fill_time",
                fill.get("timestamp", datetime.utcnow()),
            ),
            slippage_bps=fill.get("slippage_bps", 0.0),
            is_leaving_qty=fill.get("is_leaving_qty", False),
        )


class ExecutionRecord(AuditRecord):
    """
    执行成交审计记录（Phase 3 → Phase 8）。

    记录预估值与实际成交的对比，用于执行质量分析和 slippage 校正反馈。
    """

    source_phase: Literal["Phase 3"] = "Phase 3"

    # ── 执行计划引用 ────────────────────────────────
    plan_id: str = Field(..., description="关联的 PositionPlan ID")
    order_type: str = Field(..., description="订单类型：MARKET / LIMIT / VWAP / TWAP / ICEBERG / ADAPTIVE")
    algorithm: str = Field("", description="算法名称")

    # ── 预估值（Phase 7 Evaluator pre-trade） ─────────
    estimated_slippage_bps: float = Field(
        0.0, description="预估算滑点（bps）"
    )
    estimated_impact_bps: float = Field(
        0.0, description="预估市场冲击（bps）"
    )
    estimated_fill_rate: float = Field(
        1.0, ge=0, le=1, description="预估成交率（0-1）"
    )

    # ── 实际成交快照 ──────────────────────────────
    fills: List[FillSnapshot] = Field(
        default_factory=list,
        description="实际成交分片快照（FillSnapshot[]）",
    )
    total_requested_qty: float = Field(0.0, ge=0)
    total_filled_qty: float = Field(0.0, ge=0)
    fill_rate: float = Field(1.0, ge=0, le=1, description="实际成交率")
    avg_execution_price: float = Field(0.0, gt=0, description="加权平均成交价")
    arrival_price: float = Field(0.0, gt=0, description="到达价")

    # ── 实际质量指标 ──────────────────────────────
    realized_slippage_bps: float = Field(
        0.0, description="实际滑点（bps）：(avg_fill_price - arrival_price) / arrival_price × 10000"
    )
    realized_impact_bps: float = Field(
        0.0, description="实际市场冲击（bps）"
    )
    execution_quality_score: float = Field(
        0.0, ge=0, le=1, description="执行质量评分（Phase 7 Evaluator post-trade）"
    )
    quality_rating: ExecutionQuality = Field(
        ExecutionQuality.FAIR, description="质量等级"
    )

    # ── 时间维度 ────────────────────────────────
    execution_start: Optional[datetime] = Field(None)
    execution_end: Optional[datetime] = Field(None)
    execution_duration_seconds: Optional[float] = Field(
        None, description="执行总时长（秒）"
    )

    # ── 关联 ───────────────────────────────────────
    position_plan_id: Optional[str] = Field(
        None, description="关联的 PositionPlan ID"
    )
