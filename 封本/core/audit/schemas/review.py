"""Review — 人工复盘对象（与系统生成的 Feedback 完全独立）。"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    """复盘状态（独立于 Feedback 状态机）。"""
    PENDING = "pending"       # 待复盘
    IN_PROGRESS = "in_progress"  # 复盘中
    COMPLETED = "completed"   # 已完成
    DISPUTED = "disputed"     # 有异议


class Review(BaseModel):
    """
    人工复盘对象。

    Review（人工复盘）与 Feedback（系统聚合反馈）的职责边界：
    - Review：人工填写，包含主观评分、批注、决策说明
    - Feedback：系统自动聚合，不含人工主观评分，不替代 Review

    Review 可引用 AuditRecord 作为证据，但不修改 AuditRecord 本身。
    """

    review_id: str = Field(..., description="复盘记录 ID（UUID）")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # ── 引用 ────────────────────────────────────────
    audit_id: str = Field(..., description="关联的审计记录 ID")
    review_type: Literal["decision", "execution"] = Field(
        ..., description="复盘类型"
    )

    # ── 复盘人 ───────────────────────────────────
    reviewer: str = Field(
        default="human", description="复盘人（human / agent_name）"
    )

    # ── 评分 ─────────────────────────────────────
    accuracy_score: float = Field(
        0.0, ge=0, le=1,
        description="决策准确性评分（人工）",
    )
    notes: str = Field("", description="人工复盘批注")

    # ── 分类结论 ─────────────────────────────────
    verdict: Literal[
        "correct",     # 决策正确
        "incorrect",   # 决策错误
        "lucky",      # 结果正确但决策过程有问题
        "unlucky",     # 结果错误但决策过程合理
        "inconclusive",  # 无法判断
    ] = Field("inconclusive")

    # ── 标签 ─────────────────────────────────────
    tags: List[str] = Field(default_factory=list)
    status: ReviewStatus = Field(ReviewStatus.PENDING)

    # ── 时间 ─────────────────────────────────────
    reviewed_at: Optional[datetime] = Field(None)
