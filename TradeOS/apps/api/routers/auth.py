"""
apps/api/routers/auth.py 鈥?鏉冮檺涓庡璁″彧璇荤鐐?

GET  /auth/audit              鈥?鏌ヨ瀹¤杞ㄨ抗锛堝彧璇伙級
GET  /auth/users              鈥?鍒楀嚭鐢ㄦ埛锛堝彧璇伙級
GET  /auth/users/{user_id}    鈥?鏌ヨ鍗曚釜鐢ㄦ埛锛堝彧璇伙級

绾︽潫锛?
- 鎵€鏈夌鐐瑰彧璇伙紝涓嶅厑璁镐慨鏀?/ 鍒犻櫎鍘嗗彶璁板綍
- audit_entries 琛?append-only锛孮uery AuditEntry 绂佹浠讳綍鍐欐搷浣?
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


# 鈹€鈹€ DTO 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

class AuditEntryView(BaseModel):
    """AuditEntry 鍙瑙嗗浘锛堜笌鏍稿績 AuditEntry 瀹屽叏瑙ｈ€︼級銆?"""

    id: str
    timestamp: datetime
    user_id: str
    action: str
    resource: str
    detail: Optional[str] = None
    result: str
    note: Optional[str] = None


class AuditTrailResponse(BaseModel):
    """GET /auth/audit 鍝嶅簲銆?"""

    ok: bool = True
    entries: list[AuditEntryView]
    total: int
    limit: int


class UserView(BaseModel):
    """User 鍙瑙嗗浘锛堜笉鏆撮湶瀵嗙爜绛夋晱鎰熷瓧娈碉級銆?"""

    id: str
    username: str
    role: str
    is_active: bool
    description: Optional[str] = None


class UserListResponse(BaseModel):
    """GET /auth/users 鍝嶅簲銆?"""

    ok: bool = True
    users: list[UserView]


# 鈹€鈹€ 绔偣 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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
    user_id: Optional[str] = Query(default=None, description="User ID filter"),
    resource: Optional[str] = Query(default=None, description="Resource filter"),
    _: User = require_read,
) -> AuditTrailResponse:
    """
    鏌ヨ鎿嶄綔瀹¤杞ㄨ抗锛堝彧璇伙級銆?

    绂佹浠讳綍鍐欐搷浣滐紙PUT / DELETE / PATCH锛夈€?
    append-only 璇箟淇濊瘉鍘嗗彶涓嶅彲绡℃敼銆?
    """
    auth = get_auth_service()
    entries = auth.query_audit(
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
    """鍒楀嚭鎵€鏈夋椿璺冪敤鎴凤紙鍙锛夈€?"""
    auth = get_auth_service()
    users = auth.list_users()

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
    """鏌ヨ鍗曚釜鐢ㄦ埛淇℃伅锛堝彧璇伙級銆?"""
    auth = get_auth_service()
    user = auth.get_user(user_id)
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
