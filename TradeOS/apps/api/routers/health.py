"""
apps/api/routers/health.py — 健康检查与版本
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from apps.dto.api.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    服务健康检查。

    返回：
      - status: 'ok'（所有服务正常）/ 'degraded'（部分降级）
      - services: 各子服务状态
    """
    # 基础健康检查（未来可扩展为 dependency check）
    services = {
        "api": "ok",
        "arbitration": "ok",
        "risk": "ok",
        "audit": "ok",
        "strategy_pool": "ok",
    }

    all_ok = all(v == "ok" for v in services.values())

    return HealthResponse(
        status="ok" if all_ok else "degraded",
        timestamp=datetime.utcnow(),
        version=_get_version(),
        environment=_get_env(),
        services=services,
    )


@router.get("/version")
async def version_info() -> dict:
    """系统版本信息。"""
    return {
        "version": _get_version(),
        "environment": _get_env(),
        "api": "productization-layer",
    }


def _get_version() -> str:
    try:
        from infra.config.settings import get_settings
        return get_settings().version
    except Exception:
        return "1.0.0"


def _get_env() -> str:
    try:
        from infra.config.settings import get_settings
        return get_settings().env
    except Exception:
        return "dev"
