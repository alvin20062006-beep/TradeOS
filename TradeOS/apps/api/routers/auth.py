"""
apps/api/routers/auth.py — 权限与审计只读端点

GET  /auth/audit              — 查询审计轨迹（只读）
GET  /auth/users              — 列出用户（只读）
GET  /auth/users/{user_id}    — 查询单个用户（只读）

约束：
- 所有端点只读，不允许修改 / 删除历史记录
- audit_entries 表 append-only，Query AuditEntry 禁止任何写操作
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from apps.auth import get_auth_service, User
from apps.auth.dependencies import require_read
from apps.dto.api.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── DTO ─────────────────────────────────────────────────────

class AuditEntryView(BaseModel):
    """AuditEntry 只读视图（与核心 AuditEntry 完全解耦）。"""

    id: str
    timestamp: datetime
    user_id: str
    action: str
    resource: str
    detail: Optional[str] = None
    result: str
    note: Optional[str] = None


class AuditTrailResponse(BaseModel):
    """GET /auth/audit 响应。"""

    ok: bool = True
    entries: list[AuditEntryView]
    total: int
    limit: int


class UserView(BaseModel):
    """User 只读视图（不暴露密码等敏感字段）。"""

    id: str
    username: str
    role: str
    is_active: bool
    description: Optional[str] = None


class UserListResponse(BaseModel):
    """GET /auth/users 响应。"""

    ok: bool = True
    users: list[UserView]


# ── 端点 ─────────────────────────────────────────────────────

@router.get(
    "/audit",
    response_model=AuditTrailResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_audit_trail(
    limit: int = Query(default=100, ge=1, le=500),
    user_id: Optional[str] = Query(default=None, description="用户 ID 筛选"),
    resource: Optional[str] = Query(default=None, description="资源类型筛选"),
    _: User = require_read,
) -> AuditTrailResponse:
    """
    查询操作审计轨迹（只读）。

    禁止任何写操作（PUT / DELETE / PATCH）。
    append-only 语义保证历史不可篡改。
    """
    auth = get_auth_service()
    entries = auth._repo.query_audit(
        user_id=user_id,
        resource=resource,
        limit=limit,
    )

    views = [
        AuditEntryView(
            id=e.id,
            timestamp=e.timestamp,
            user_id=e.user_id,
            action=e.action,
            resource=e.resource,
            detail=e.detail,
            result=e.result,
            note=e.note,
        )
        for e in entries
    ]

    return AuditTrailResponse(
        ok=True,
        entries=views,
        total=len(views),
        limit=limit,
    )


@router.get(
    "/users",
    response_model=UserListResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def list_users(
    _: User = require_read,
) -> UserListResponse:
    """列出所有活跃用户（只读）。"""
    auth = get_auth_service()
    users = auth._repo.list_users()

    return UserListResponse(
        ok=True,
        users=[
            UserView(
                id=u.id,
                username=u.username,
                role=u.role.value,
                is_active=u.is_active,
                description=u.description,
            )
            for u in users
        ],
    )


@router.get(
    "/users/{user_id}",
    response_model=UserView,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_user(
    user_id: str,
    _: User = require_read,
) -> UserView:
    """查询单个用户信息（只读）。"""
    auth = get_auth_service()
    user = auth._repo.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "user_id": user_id},
        )

    return UserView(
        id=user.id,
        username=user.username,
        role=user.role.value,
        is_active=user.is_active,
        description=user.description,
    )
