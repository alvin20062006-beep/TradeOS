"""
apps/dto/api/common.py — 通用 API DTO
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


# ── 分页 ────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    """查询参数。"""

    limit: int = Field(default=20, ge=1, le=500, description="最大返回条数")
    offset: int = Field(default=0, ge=0, description="跳过条数")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应。"""

    items: list[T]
    total: int = Field(ge=0)
    limit: int
    offset: int
    has_more: bool = Field(description="是否还有更多")


# ── 健康检查 ────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """GET /health 响应。"""

    status: str = Field(description="'ok' 或 'degraded'")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    environment: str
    services: dict[str, str] = Field(
        default_factory=dict,
        description="各子服务健康状态 {'arbitration': 'ok', 'risk': 'ok', ...}",
    )


# ── 错误 ────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    """错误详情。"""

    error: str = Field(description="错误类型代码")
    message: str = Field(description="人类可读消息")
    detail: dict[str, Any] | None = Field(default=None, description="技术细节")
    request_id: str | None = Field(default=None, description="请求追踪 ID")


class ErrorResponse(BaseModel):
    """标准错误响应。"""

    ok: bool = Field(default=False)
    error: ErrorDetail
