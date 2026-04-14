"""
NautilusRouter - execution routing facade for the Nautilus-backed floor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ai_trading_tool.core.execution.base import ExecutionRouter
from ai_trading_tool.core.execution.enums import ExecutionMode
from ai_trading_tool.core.execution.models import ExecutionIntent
from ai_trading_tool.core.execution.nautilus import NAUTILUS_AVAILABLE

if TYPE_CHECKING:
    from ai_trading_tool.core.execution.base import ExecutionEngine
    from ai_trading_tool.core.execution.nautilus.adapter import NautilusAdapter


class NautilusRouter(ExecutionRouter):
    """Route execution intents to venue-specific Nautilus adapters."""

    def __init__(self, mode: ExecutionMode = ExecutionMode.BACKTEST):
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError(
                "NautilusTrader not available. "
                "Install with: pip install nautilus-trader"
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

    def register_engine(
        self,
        venue: str,
        engine: ExecutionEngine,
        priority: int = 0,
    ) -> None:
        self._engines[venue] = engine
        if not self._default_venue:
            self._default_venue = venue

    def get_default_engine(self) -> ExecutionEngine:
        if not self._default_venue:
            raise RuntimeError("No default engine configured")
        return self._engines[self._default_venue]

    def unregister_engine(self, venue: str) -> bool:
        if venue not in self._engines:
            return False
        del self._engines[venue]
        if self._default_venue == venue:
            self._default_venue = next(iter(self._engines), None)
        return True

    def get_engine(self, venue: str) -> Optional[ExecutionEngine]:
        return self._engines.get(venue)

    def list_engines(self) -> list[str]:
        return list(self._engines.keys())

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

    def get_default_venue(self) -> Optional[str]:
        return self._default_venue

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @mode.setter
    def mode(self, value: ExecutionMode) -> None:
        self._mode = value

    @property
    def is_running(self) -> bool:
        return any(getattr(engine, "is_running", False) for engine in self._engines.values())
