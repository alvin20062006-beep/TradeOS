"""Execution router implementations."""

from __future__ import annotations

from typing import Optional

from core.execution.base import ExecutionEngine, ExecutionRouter
from core.execution.enums import ExecutionMode
from core.execution.models import ExecutionIntent
from core.execution.nautilus import NAUTILUS_AVAILABLE
from core.execution.sinks import ExecutionEventSink, MemoryEventSink
from core.execution.simulation import SimulationExecutionEngine

if NAUTILUS_AVAILABLE:
    from core.execution.nautilus.adapter import NautilusAdapter
else:
    NautilusAdapter = None  # type: ignore[assignment]


class SimulationRouter(ExecutionRouter):
    """Venue router backed by the local simulation engine."""

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SIMULATION,
        *,
        sink: Optional[ExecutionEventSink] = None,
        venue: str = "SIMULATED",
    ) -> None:
        self._mode = mode
        self._engines: dict[str, ExecutionEngine] = {}
        self._default_venue: Optional[str] = None
        self.register_engine(venue, SimulationExecutionEngine(mode=mode, sink=sink or MemoryEventSink(), venue=venue))

    async def route(self, intent: ExecutionIntent) -> ExecutionEngine:
        venue = intent.venue or self._default_venue
        if not venue:
            raise ValueError("No venue specified and no default venue configured")
        if venue not in self._engines:
            raise RuntimeError(f"No engine configured for venue: {venue}")
        return self._engines[venue]

    def register_engine(self, venue: str, engine: ExecutionEngine, priority: int = 0) -> None:
        self._engines[venue] = engine
        if self._default_venue is None:
            self._default_venue = venue

    def get_default_engine(self) -> ExecutionEngine:
        if self._default_venue is None:
            raise RuntimeError("No default engine configured")
        return self._engines[self._default_venue]

    def get_engine(self, venue: str) -> Optional[ExecutionEngine]:
        return self._engines.get(venue)

    def list_engines(self) -> list[str]:
        return list(self._engines)

    async def start_all(self) -> None:
        for engine in self._engines.values():
            await engine.start()

    async def stop_all(self) -> None:
        for engine in self._engines.values():
            await engine.stop()

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @mode.setter
    def mode(self, value: ExecutionMode) -> None:
        self._mode = value

    @property
    def is_running(self) -> bool:
        return any(getattr(engine, "is_running", False) for engine in self._engines.values())


class NautilusRouter(ExecutionRouter):
    """Route execution intents to venue-specific Nautilus adapters."""

    def __init__(self, mode: ExecutionMode = ExecutionMode.LIVE):
        if not NAUTILUS_AVAILABLE or NautilusAdapter is None:
            raise RuntimeError(
                "NautilusTrader not available. Install with: pip install nautilus-trader"
            )
        self._mode = mode
        self._engines: dict[str, NautilusAdapter] = {}
        self._default_venue: Optional[str] = None

    async def route(self, intent: ExecutionIntent) -> ExecutionEngine:
        venue = intent.venue or self._default_venue
        if not venue:
            raise ValueError("No venue specified and no default venue configured")
        if venue not in self._engines:
            raise RuntimeError(f"No engine configured for venue: {venue}")
        return self._engines[venue]

    def register_engine(self, venue: str, engine: ExecutionEngine, priority: int = 0) -> None:
        self._engines[venue] = engine  # type: ignore[assignment]
        if self._default_venue is None:
            self._default_venue = venue

    def get_default_engine(self) -> ExecutionEngine:
        if self._default_venue is None:
            raise RuntimeError("No default engine configured")
        return self._engines[self._default_venue]

    def get_engine(self, venue: str) -> Optional[ExecutionEngine]:
        return self._engines.get(venue)

    def list_engines(self) -> list[str]:
        return list(self._engines)

    async def start_all(self) -> None:
        for engine in self._engines.values():
            await engine.start()

    async def stop_all(self) -> None:
        for engine in self._engines.values():
            await engine.stop()

    def set_default_venue(self, venue: str) -> None:
        if venue not in self._engines:
            raise ValueError(f"Venue not registered: {venue}")
        self._default_venue = venue

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @mode.setter
    def mode(self, value: ExecutionMode) -> None:
        self._mode = value

    @property
    def is_running(self) -> bool:
        return any(getattr(engine, "is_running", False) for engine in self._engines.values())


def build_default_router(
    mode: ExecutionMode = ExecutionMode.SIMULATION,
    *,
    sink: Optional[ExecutionEventSink] = None,
    venue: str = "SIMULATED",
) -> ExecutionRouter:
    """Build a runnable router for the requested mode."""
    if mode in {ExecutionMode.SIMULATION, ExecutionMode.BACKTEST, ExecutionMode.PAPER}:
        return SimulationRouter(mode=mode, sink=sink, venue=venue)
    return NautilusRouter(mode=mode)
