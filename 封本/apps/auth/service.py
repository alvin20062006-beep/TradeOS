"""
apps/auth/service.py — 权限校验服务
"""

from __future__ import annotations

import logging
from typing import Optional

from apps.auth.models import OperatorRole, has_permission, User
from apps.auth.repository import AuthRepository

logger = logging.getLogger(__name__)


class AuthService:
    """
    权限校验服务。

    - dev 环境（auth_enabled=False）：返回默认 operator 角色（旁路 auth）
    - prod 环境（auth_enabled=True）：查询 SQLite 用户表，校验角色权限
    """

    def __init__(self, repo: Optional[AuthRepository] = None) -> None:
        self._repo = repo or AuthRepository()
        self._auth_enabled: Optional[bool] = None  # 延迟加载

    @property
    def auth_enabled(self) -> bool:
        if self._auth_enabled is None:
            try:
                from infra.config.settings import get_settings

                self._auth_enabled = get_settings().auth_enabled
            except Exception:
                self._auth_enabled = False
        return self._auth_enabled

    def get_user(self, user_id: str) -> Optional[User]:
        if not self.auth_enabled:
            # dev 环境：返回默认 operator
            return User(
                id="dev-operator",
                username="dev-operator",
                role=OperatorRole.OPERATOR,
                description="Dev environment bypass",
            )
        return self._repo.get_user(user_id)

    def check_permission(self, user_id: str, action: str) -> tuple[bool, Optional[str]]:
        """
        校验用户是否有指定操作的权限。

        Returns:
            (allowed, reason_if_denied)
        """
        if not self.auth_enabled:
            # dev 环境：全部放行
            return True, None

        user = self._repo.get_user(user_id)
        if user is None:
            return False, "User not found or inactive"

        if not has_permission(user.role, action):
            return False, f"Role '{user.role.value}' lacks '{action}' permission"

        return True, None

    def require_permission(self, user_id: str, action: str) -> User:
        """
        校验权限，失败则抛出 HTTPException。

        Raises:
            401 — 用户不存在
            403 — 权限不足
        """
        from fastapi import HTTPException

        allowed, reason = self.check_permission(user_id, action)
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "reason": reason,
                    "user_id": user_id,
                    "action": action,
                },
            )

        user = self.get_user(user_id)
        assert user is not None
        return user

    def log(self, user_id: str, action: str, resource: str, **kwargs) -> None:
        """写审计日志（append-only，始终记录）。"""
        try:
            result = kwargs.pop("result", "accepted")
            note = kwargs.pop("note", None)
            self._repo.log_audit(
                user_id=user_id,
                action=action,
                resource=resource,
                detail=kwargs or None,
                result=result,
                note=note,
            )
        except Exception as e:
            # 审计日志失败不阻断主流程
            logger.warning("Audit log failed: %s", e)
