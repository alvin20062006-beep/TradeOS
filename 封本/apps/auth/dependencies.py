"""
apps/auth/dependencies.py — FastAPI 依赖注入

从请求头提取 user_id，校验权限，返回 User 模型。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from apps.auth.models import OperatorRole, User
from apps.auth.service import AuthService

# ── 全局 service 单例 ──────────────────────────────────────

_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# ── 依赖注入 ───────────────────────────────────────────────

async def get_current_user(
    x_user_id: Annotated[str | None, Header()] = None,
    auth: AuthService = Depends(get_auth_service),
) -> User:
    """
    从 X-User-ID header 获取当前用户。

    dev 环境（auth_enabled=False）：自动返回 operator 角色，无需传 header。
    prod 环境（auth_enabled=True）：必须传 X-User-ID。
    """
    if not auth.auth_enabled:
        # dev 环境：旁路 auth
        return User(
            id="dev-operator",
            username="dev-operator",
            role=OperatorRole.OPERATOR,
            description="Dev environment bypass",
        )

    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "message": "X-User-ID header required in prod mode",
            },
        )

    user = auth.get_user(x_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "user_not_found", "user_id": x_user_id},
        )

    return user


async def require_read(user: User = Depends(get_current_user)) -> User:
    """读权限依赖。GET 端点使用。"""
    return user


async def require_suggest(user: User = Depends(get_current_user)) -> User:
    """写权限依赖。POST suggestion-only 端点使用。"""
    auth = get_auth_service()
    auth.require_permission(user.id, "suggest")
    return user


async def require_task(user: User = Depends(get_current_user)) -> User:
    """Task 权限依赖。POST task-style 端点使用。"""
    auth = get_auth_service()
    auth.require_permission(user.id, "task")
    return user


async def require_review(user: User = Depends(get_current_user)) -> User:
    """复盘确认权限。ReviewManager.apply() 端点使用。"""
    auth = get_auth_service()
    auth.require_permission(user.id, "review")
    return user
