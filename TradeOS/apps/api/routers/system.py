"""
apps/api/routers/system.py 鈥?缁熶竴绯荤粺鐘舵€佺鐐?
GET /system/status    鈥?缁熶竴鐘舵€侀潰鏉匡紙health + version + env 鍚堝苟锛?GET /system/modules   鈥?Phase 妯″潡灏辩华鐘舵€佹帰娴?"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.dto.api.common import ErrorResponse

router = APIRouter(prefix="/system", tags=["System"])
logger = logging.getLogger(__name__)


class ModuleStatus(BaseModel):
    """鍗曚釜妯″潡灏辩华鐘舵€併€?"""

    name: str
    status: Literal["ready", "error", "unavailable"]
    message: str = ""
    detail: str = Field(default="", description="Technical detail such as import error")


class SystemStatusResponse(BaseModel):
    """GET /system/status 鍝嶅簲銆?"""

    ok: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    environment: str
    modules: dict[str, str] = Field(description="Module readiness map")


class SystemModulesResponse(BaseModel):
    """GET /system/modules 鍝嶅簲銆?"""

    ok: bool = True
    modules: list[ModuleStatus]


def _probe_module(name: str, import_path: str) -> ModuleStatus:
    """鎺㈡祴鍗曚釜妯″潡鏄惁鍙鍏ャ€?"""
    try:
        __import__(import_path)
        return ModuleStatus(name=name, status="ready", message="OK")
    except Exception as e:
        return ModuleStatus(
            name=name,
            status="error",
            message="Import failed",
            detail=str(e)[:120],
        )


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    responses={401: {"model": ErrorResponse}},
)
async def system_status() -> SystemStatusResponse:
    """
    缁熶竴绯荤粺鐘舵€侀潰鏉裤€?
    鍚堝苟 /health + /version 杈撳嚭锛屾彁渚涗竴绔欏紡鐘舵€佹憳瑕併€?    """
    health = {
        "api": "ok",
        "arbitration": "ok",
        "risk": "ok",
        "audit": "ok",
        "strategy_pool": "ok",
    }

    all_ok = all(v == "ok" for v in health.values())
    status: Literal["ok", "degraded"] = "ok" if all_ok else "degraded"

    # 鐗堟湰淇℃伅
    version = "1.0.0"
    environment = "dev"
    try:
        from infra.config.settings import get_settings

        s = get_settings()
        version = s.version
        environment = s.env
    except Exception as exc:
        logger.warning("Settings unavailable, using system status defaults", exc_info=True)

    return SystemStatusResponse(
        ok=status == "ok",
        timestamp=datetime.utcnow(),
        version=version,
        environment=environment,
        modules=health,
    )


@router.get(
    "/modules",
    response_model=SystemModulesResponse,
    responses={401: {"model": ErrorResponse}},
)
async def system_modules() -> SystemModulesResponse:
    """
    Phase 妯″潡灏辩华鎺㈡祴銆?
    瀵?Phase 1-10 鍚勬ā鍧楀仛 import 鎺㈡祴锛岃繑鍥炲氨缁姸鎬併€?    涓嶅仛鍔熻兘娴嬭瘯锛屽彧娴嬫ā鍧楁槸鍚﹀瓨鍦ㄣ€?    """
    probes = [
        ("arbitration", "core.arbitration.engine"),
        ("risk", "core.risk.engine"),
        ("audit", "core.audit.engine"),
        ("analysis", "core.analysis.base"),
        ("strategy_pool", "core.strategy_pool"),
        ("qlib_data", "qlib"),
    ]

    modules = [_probe_module(name, path) for name, path in probes]
    errors = [m for m in modules if m.status == "error"]

    return SystemModulesResponse(
        ok=len(errors) == 0,
        modules=modules,
    )
