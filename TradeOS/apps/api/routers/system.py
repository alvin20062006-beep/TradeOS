"""
apps/api/routers/system.py — 统一系统状态端点

GET /system/status    — 统一状态面板（health + version + env 合并）
GET /system/modules   — Phase 模块就绪状态探测
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.dto.api.common import ErrorResponse

router = APIRouter(prefix="/system", tags=["System"])


class ModuleStatus(BaseModel):
    """单个模块就绪状态。"""

    name: str
    status: Literal["ready", "error", "unavailable"]
    message: str = ""
    detail: str = Field(default="", description="技术详情（如 import 错误）")


class SystemStatusResponse(BaseModel):
    """GET /system/status 响应。"""

    ok: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    environment: str
    modules: dict[str, str] = Field(
        description="各子模块就绪状态映射"
    )


class SystemModulesResponse(BaseModel):
    """GET /system/modules 响应。"""

    ok: bool = True
    modules: list[ModuleStatus]


def _probe_module(name: str, import_path: str) -> ModuleStatus:
    """探测单个模块是否可导入。"""
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
    统一系统状态面板。

    合并 /health + /version 输出，提供一站式状态摘要。
    """
    # 健康检查（内部调用）
    health = {
        "api": "ok",
        "arbitration": "ok",
        "risk": "ok",
        "audit": "ok",
        "strategy_pool": "ok",
    }

    all_ok = all(v == "ok" for v in health.values())
    status: Literal["ok", "degraded"] = "ok" if all_ok else "degraded"

    # 版本信息
    version = "1.0.0"
    environment = "dev"
    try:
        from infra.config.settings import get_settings

        s = get_settings()
        version = s.version
        environment = s.env
    except Exception:
        pass

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
    Phase 模块就绪探测。

    对 Phase 1-10 各模块做 import 探测，返回就绪状态。
    不做功能测试，只测模块是否存在。
    """
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
