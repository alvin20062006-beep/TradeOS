"""
apps/auth/models.py — 轻量权限模型（首批基线）

技术选型：SQLite + local users（不做 OAuth / JWT / Keycloak）
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ── 角色枚举 ────────────────────────────────────────────────

class OperatorRole(str, Enum):
    """用户角色枚举（首批基线）。"""

    VIEWER = "viewer"      # 只读
    OPERATOR = "operator"  # 可写 suggestion-only
    ADMIN = "admin"        # 含人工复盘确认权限


# ── 数据模型 ────────────────────────────────────────────────

class User(BaseModel):
    """用户模型。"""

    id: str = Field(description="用户 ID")
    username: str = Field(description="用户名")
    role: OperatorRole = Field(description="角色")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None, description="用途说明（如 AI operator）")


class AuditEntry(BaseModel):
    """操作审计条目。"""

    id: str
    timestamp: datetime
    user_id: str
    action: str              # "POST /arbitration/run"
    resource: str            # "arbitration"
    detail: Optional[str]    # JSON 序列化参数摘要
    result: str              # "accepted" / "rejected" / "error"
    note: Optional[str]      # 拒绝/错误原因


# ── 权限矩阵 ────────────────────────────────────────────────

PERMISSION_MATRIX: dict[OperatorRole, set[str]] = {
    OperatorRole.VIEWER: {
        "read",           # GET 端点
    },
    OperatorRole.OPERATOR: {
        "read",
        "suggest",        # POST suggestion-only 端点（analysis / arbitration / risk）
        "task",           # POST task-style 端点（feedback scan）
    },
    OperatorRole.ADMIN: {
        "read",
        "suggest",
        "task",
        "review",         # 人工复盘确认权限（ReviewManager apply）
    },
}


def has_permission(role: OperatorRole, action: str) -> bool:
    """
    权限校验。

    action 与端点类型的映射：
      "read"    → GET 端点
      "suggest" → POST /analysis/run, /arbitration/run, /risk/calculate, /strategy-pool/propose
      "task"    → POST /audit/feedback/tasks
      "review"  → ReviewManager.apply()

    注意：FeedbackRegistry 写入由 append-only 设计保证，非权限控制点。
    """
    return action in PERMISSION_MATRIX.get(role, set())
