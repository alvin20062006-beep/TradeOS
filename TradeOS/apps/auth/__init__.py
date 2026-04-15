"""apps/auth/__init__.py — 轻量权限层（首批基线）"""

from apps.auth.dependencies import (
    get_auth_service,
    get_current_user,
    require_read,
    require_review,
    require_suggest,
    require_task,
)
from apps.auth.models import OperatorRole, User, has_permission, PERMISSION_MATRIX
from apps.auth.repository import AuthRepository
from apps.auth.service import AuthService

__all__ = [
    "AuthService",
    "AuthRepository",
    "get_auth_service",
    "get_current_user",
    "has_permission",
    "OperatorRole",
    "PERMISSION_MATRIX",
    "require_read",
    "require_review",
    "require_suggest",
    "require_task",
    "User",
]
