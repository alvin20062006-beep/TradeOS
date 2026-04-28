"""
apps/api/main.py - FastAPI application factory + web console mount.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.api.routers import (
    health,
    analysis,
    arbitration,
    risk,
    audit,
    strategy_pool,
    pipeline,
    data_sources,
    system,
    auth,
)

app = FastAPI(
    title="TradeOS",
    version="1.0.0",
    description="TradeOS local product API backed by the Phase 1-10 Python/FastAPI core.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)  # /health, /version
app.include_router(system.router)  # /system/status, /system/modules
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(arbitration.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(strategy_pool.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(data_sources.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")  # /auth/audit, /auth/users

WEB_CONSOLE_DIR = Path(__file__).resolve().parents[1] / "web_console"
app.mount("/console", StaticFiles(directory=WEB_CONSOLE_DIR, html=True), name="web_console")


@app.get("/")
async def root():
    return {
        "message": "TradeOS API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "/system/status",
        "console": "/console/",
        "product_entry": "TradeOS desktop shell",
        "advanced_surface": "Diagnostics / Advanced API",
        "legacy_fallback": "apps/console/",
    }
