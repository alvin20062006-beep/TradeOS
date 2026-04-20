"""Execution runtime orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.execution.base import ExecutionRouter
from core.execution.enums import EngineStatus, ExecutionMode
from core.execution.models import ExecutionIntent, ExecutionResult, RuntimeReport
from core.execution.router import build_default_router
from core.execution.sinks import ExecutionEventSink


class ExecutionRuntime:
    """Lifecycle manager for execution routing and engine dispatch."""

    def __init__(
        self,
        router: Optional[ExecutionRouter] = None,
        *,
        mode: ExecutionMode = ExecutionMode.SIMULATION,
        sink: Optional[ExecutionEventSink] = None,
        venue: str = "SIMULATED",
    ) -> None:
        self._mode = mode
        self._router = router or build_default_router(mode=mode, sink=sink, venue=venue)
        self._status = EngineStatus.STOPPED
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[datetime] = None

    async def start(self) -> None:
        if self._status == EngineStatus.RUNNING:
            return
        self._status = EngineStatus.STARTING
        try:
            if hasattr(self._router, "start_all"):
                await self._router.start_all()  # type: ignore[attr-defined]
            self._started_at = datetime.utcnow()
            self._status = EngineStatus.RUNNING
        except Exception as exc:
            self._status = EngineStatus.ERROR
            self._last_error = str(exc)
            self._last_error_at = datetime.utcnow()
            raise

    async def stop(self) -> None:
        if self._status == EngineStatus.STOPPED:
            return
        self._status = EngineStatus.STOPPING
        try:
            if hasattr(self._router, "stop_all"):
                await self._router.stop_all()  # type: ignore[attr-defined]
            self._stopped_at = datetime.utcnow()
            self._status = EngineStatus.STOPPED
        except Exception as exc:
            self._status = EngineStatus.ERROR
            self._last_error = str(exc)
            self._last_error_at = datetime.utcnow()
            raise

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def execute(self, intent: ExecutionIntent) -> ExecutionResult:
        if self._status != EngineStatus.RUNNING:
            raise RuntimeError("ExecutionRuntime is not running")
        engine = await self._router.route(intent)
        return await engine.execute_intent(intent)

    def configure(self, router: ExecutionRouter) -> None:
        if self._status == EngineStatus.RUNNING:
            raise RuntimeError("Cannot configure while runtime is running")
        self._router = router

    def health_check(self) -> RuntimeReport:
        adapter_status: dict[str, str] = {}
        total_orders = 0
        total_fills = 0

        if hasattr(self._router, "list_engines") and hasattr(self._router, "get_engine"):
            for venue in self._router.list_engines():  # type: ignore[attr-defined]
                engine = self._router.get_engine(venue)  # type: ignore[attr-defined]
                if engine is None:
                    continue
                adapter_status[venue] = "RUNNING" if getattr(engine, "is_running", False) else "STOPPED"
                total_orders += len(getattr(engine, "_orders", {}))
                total_fills += sum(len(v) for v in getattr(engine, "_fills", {}).values())

        return RuntimeReport(
            status=self._status.value,
            mode=self._mode.value,
            started_at=self._started_at.isoformat() if self._started_at else None,
            stopped_at=self._stopped_at.isoformat() if self._stopped_at else None,
            adapters=adapter_status,
            total_orders=total_orders,
            total_fills=total_fills,
            last_error=self._last_error,
            last_error_at=self._last_error_at.isoformat() if self._last_error_at else None,
        )

    @property
    def router(self) -> ExecutionRouter:
        return self._router

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @mode.setter
    def mode(self, value: ExecutionMode) -> None:
        self._mode = value

    @property
    def is_running(self) -> bool:
        return self._status == EngineStatus.RUNNING
