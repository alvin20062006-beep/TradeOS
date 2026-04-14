"""AuditRecord — 所有审计记录的顶层抽象基类（append-only）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    """
    所有审计记录的抽象基类。

    append-only 原则：
    - 记录一旦写入不可修改，不可删除
    - 只追加新记录，通过 revision_id 或 successor 字段表达版本变更
    - 错误记录通过新记录中的 correction_of 字段引用旧记录来修正

    子类：DecisionRecord / ExecutionRecord / RiskAudit
    """

    audit_id: str = Field(
        ..., description="唯一审计记录 ID（UUID）"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="审计时间（UTC）",
    )
    source_phase: str = Field(
        ..., description="来源阶段：Phase 3 / Phase 6 / Phase 7"
    )
    symbol: str = Field(..., description="标的代码")
    decision_id: str = Field(
        ..., description="关联的 ArbitrationDecision ID"
    )

    class Config:
        frozen = False  # 可追加字段（runtime_id 等）
