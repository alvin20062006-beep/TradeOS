"""
apps/dto/api/audit.py — 审计层 API DTO

包含：
- DecisionRecord / RiskAudit / Feedback 查询
- Feedback 扫描任务（task-style）
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── 反馈扫描任务 ─────────────────────────────────────────────

class FeedbackScanRequest(BaseModel):
    """
    POST /audit/feedback/tasks 请求（task-style）。

    提交 Feedback 扫描任务，返回 task_id。
    任务异步执行，调用方通过 GET /audit/feedback/tasks/{task_id} 查询结果。
    """

    feedback_type: Optional[
        Literal[
            "loss_amplification",
            "win_fade",
            "regime_mismatch",
            "confidence_mismatch",
            "low_signal_count",
            "all",
        ]
    ] = Field(default="all", description="反馈类型筛选")
    symbol: Optional[str] = Field(default=None, description="标的筛选（None=全部）")
    since: Optional[datetime] = Field(default=None, description="时间范围起点")


class FeedbackScanResponse(BaseModel):
    """POST /audit/feedback/tasks 响应。"""

    ok: bool = True
    task_id: str = Field(description="任务 ID，用于后续查询")
    status: str = Field(default="accepted", description="accepted | processing | done | error")
    message: str = Field(
        default="Feedback scan task submitted. "
        "Use GET /audit/feedback/tasks/{task_id} to poll result."
    )
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackScanResult(BaseModel):
    """扫描任务结果（GET /audit/feedback/tasks/{task_id} 响应）。"""

    task_id: str
    status: str = Field(description="accepted | processing | done | error")
    feedback_count: int = Field(ge=0, description="本次扫描产生的 feedback 数量")
    feedbacks: list["FeedbackView"] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None, description="摘要信息")
    error: Optional[str] = Field(default=None, description="错误信息（error 状态时）")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ── 查询参数 ────────────────────────────────────────────────

class AuditQueryParams(BaseModel):
    """GET /audit/decisions 等查询参数。"""

    symbol: Optional[str] = Field(default=None, description="标的筛选")
    limit: int = Field(default=20, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    since: Optional[datetime] = Field(default=None, description="时间范围起点")


# ── DecisionRecord 视图 ─────────────────────────────────────

class DecisionRecordView(BaseModel):
    """
    DecisionRecord 视图（与核心 DecisionRecord 完全解耦）。

    AI 通过此 DTO 查询，禁止直接访问核心 AuditRecord 对象。
    """

    decision_id: str
    symbol: str
    timestamp: datetime
    bias: str
    confidence: float
    signal_count: int
    rules_applied: list[str] = Field(default_factory=list)
    audit_id: str = Field(description="审计记录 ID")
    source: str = Field(default="arbitration", description="来源")


# ── RiskAudit 视图 ─────────────────────────────────────────

class RiskAuditView(BaseModel):
    """RiskAudit 视图（与核心 RiskAudit 完全解耦）。"""

    plan_id: str
    symbol: str
    timestamp: datetime
    final_quantity: float
    veto_triggered: bool
    limit_checks: list["LimitCheckView"] = Field(default_factory=list)
    audit_id: str
    source: str = Field(default="risk", description="来源")


class LimitCheckView(BaseModel):
    """风控限制检查结果（共享视图，可被 risk/audit 共用）。"""

    filter_name: str = Field(description="过滤器名称")
    passed: bool = Field(description="是否通过")
    mode: str = Field(description="open | reduce | exit")
    raw_qty: float = Field(description="原始数量（调整前）")
    adjusted_qty: float = Field(description="调整后数量（cap 后）")
    reason: str = Field(description="通过 / 拒绝 / 调整原因")


# ── Feedback 视图 ────────────────────────────────────────────

class FeedbackView(BaseModel):
    """
    Feedback 视图（与核心 Feedback 完全解耦）。

    AI 通过此 DTO 查询，禁止直接访问核心 Feedback 对象。
    """

    feedback_id: str
    feedback_type: str = Field(description="loss_amplification | win_fade | ...")
    severity: str = Field(description="info | warning | critical")
    description: str = Field(description="反馈描述")
    symbol: Optional[str] = Field(default=None)
    decision_id: Optional[str] = Field(default=None)
    created_at: datetime
    metadata: dict = Field(default_factory=dict)


# ── 响应 ────────────────────────────────────────────────────

class AuditQueryResponse(BaseModel):
    """GET /audit/decisions 等响应。"""

    ok: bool = True
    items: list[DecisionRecordView | RiskAuditView | FeedbackView]
    total: int
    limit: int
    offset: int
    has_more: bool


# 修复 forward reference
FeedbackScanResult.model_rebuild()
FeedbackView.model_rebuild()
DecisionRecordView.model_rebuild()
RiskAuditView.model_rebuild()
