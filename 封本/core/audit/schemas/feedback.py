"""Feedback — 系统聚合生成的机器反馈（与人工 Review 完全独立）。"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """
    Feedback 类型，决定回流到 Phase 4 的哪条链路。

    与人工 Review 的边界：
    - Feedback 由系统自动聚合，基于量化统计
    - Review 由人工填写，包含主观判断
    - Feedback 不能替代 Review，两者互补
    """

    SLIPPAGE_CALIBRATION = "slippage_calibration"  # → slippage 模型重校准
    SIGNAL_DECAY = "signal_decay"                  # → 标签窗口重设计
    FILTER_PATTERN = "filter_pattern"               # → 风控阈值调整 / 模型重训
    FACTOR_ATTRIBUTION = "factor_attribution"       # → Alpha 因子评估


class FeedbackStatus(str, Enum):
    """
    Feedback 状态机。

    Phase 4 updater 不直接应用 feedback，只输出建议。
    人工确认后，才将 status 改为 applied。
    """

    PENDING = "pending"     # 待处理
    REVIEWED = "reviewed"   # 已复核
    APPLIED = "applied"     # 已应用（人工确认后）
    REJECTED = "rejected"   # 已拒绝


class Feedback(BaseModel):
    """
    系统聚合生成的机器反馈（回流 Phase 4）。

    由 FeedbackEngine 扫描 AuditRecord 自动生成。
    不含人工主观评分，不替代 Review。
    """

    feedback_id: str = Field(..., description="Feedback ID（UUID）")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # ── 类型 ─────────────────────────────────────
    feedback_type: FeedbackType
    severity: Literal["low", "medium", "high"] = Field("medium")

    # ── 证据 ─────────────────────────────────────
    symbol: Optional[str] = Field(None, description="标的（symbol-specific 时填）")
    sample_size: int = Field(
        0, description="生成此 feedback 依据的样本数量"
    )
    evidence: Dict = Field(
        default_factory=dict,
        description="量化证据（供人工复核）：{metric_name: value, ...}",
    )

    # ── 量化结论 ───────────────────────────────
    metric_name: str = Field(..., description="指标名：e.g. realized_slippage_bps")
    metric_value: float = Field(0.0, description="指标当前值")
    threshold_breach: bool = Field(
        False, description="是否超过阈值"
    )

    # ── 建议动作 ───────────────────────────────
    suggested_action: str = Field(
        "", description="建议动作描述（供人工参考，不直接执行）"
    )
    confidence: float = Field(
        0.5, ge=0, le=1,
        description="Feedback 置信度（0-1）",
    )

    # ── 关联审计记录 ──────────────────────────
    source_audit_ids: List[str] = Field(
        default_factory=list,
        description="生成此 feedback 依据的 AuditRecord ID 列表",
    )

    # ── 状态机 ─────────────────────────────────
    status: FeedbackStatus = Field(FeedbackStatus.PENDING)
    reviewed_by: Optional[str] = Field(
        None, description="人工复核者"
    )
    reviewed_at: Optional[datetime] = Field(None)
    applied_experiment_id: Optional[str] = Field(
        None, description="如果已应用，对应的 Phase 4 Experiment ID"
    )
    rejection_reason: Optional[str] = Field(
        None, description="拒绝原因（如果 rejected）"
    )

    # ── Phase 4 输出（建议，不直接写回 registry） ────────
    phase4_suggestion: Dict = Field(
        default_factory=dict,
        description="Phase 4 更新建议：{registry: str, field: str, value: any}（人工参考）",
    )
