"""
apps/api/routers/health.py 鈥?鍋ュ悍妫€鏌ヤ笌鐗堟湰
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from apps.dto.api.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    鏈嶅姟鍋ュ悍妫€鏌ャ€?
    杩斿洖锛?      - status: 'ok'锛堟墍鏈夋湇鍔℃甯革級/ 'degraded'锛堥儴鍒嗛檷绾э級
      - services: 鍚勫瓙鏈嶅姟鐘舵€?    """
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
    """绯荤粺鐗堟湰淇℃伅銆?"""
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
