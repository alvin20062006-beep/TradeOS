"""Execution-layer base interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Awaitable, Callable, Optional

from pydantic import BaseModel

from core.execution.enums import ExecutionMode
from core.execution.models import (
    ExecutionIntent,
    ExecutionReport,
    ExecutionResult,
    FillRecord,
    OrderRecord,
    PositionState,
)
from core.execution.sinks import ExecutionEventSink


class ExecutionEngine(ABC):
    """Unified execution engine interface."""

    def __init__(self, mode: ExecutionMode, sink: ExecutionEventSink):
        self._mode = mode
        self._sink = sink
        self._running = False

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @property
    def is_running(self) -> bool:
        return self._running

    @abstractmethod
    async def start(self) -> None:
        """Start the execution engine."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the execution engine."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return whether the engine is healthy."""

    @abstractmethod
    async def submit_intent(self, intent: ExecutionIntent) -> ExecutionReport:
        """Submit an execution intent and return the current execution report."""

    async def execute_intent(self, intent: ExecutionIntent) -> ExecutionResult:
        """Run an intent and return the concrete execution snapshot."""
        report = await self.submit_intent(intent)
        order = await self.get_order(report.order_id) if report.order_id else None
        fills = await self.get_fills_for_order(report.order_id) if report.order_id else []
        position = await self.get_position(intent.symbol)
        return ExecutionResult(
            intent=intent,
            report=report,
            order=order,
            fills=fills,
            position=position,
            venue=report.venue,
            mode=self.mode.value,
        )

    @abstractmethod
    async def cancel_order(
        self,
        order_id: str,
        reason: Optional[str] = None,
    ) -> ExecutionReport:
        """Cancel an order."""

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        new_quantity: Optional[Decimal] = None,
        new_price: Optional[Decimal] = None,
    ) -> ExecutionReport:
        """Modify an existing order."""

    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[OrderRecord]:
        """Fetch one order record."""

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[PositionState]:
        """Fetch one position snapshot."""

    @abstractmethod
    async def get_all_positions(self) -> list[PositionState]:
        """Fetch all positions."""

    @abstractmethod
    async def get_fills_for_order(self, order_id: str) -> list[FillRecord]:
        """Fetch all fills for one order."""

    @abstractmethod
    def on_fill(self, callback: Callable[[FillRecord], Awaitable[None]]) -> None:
        """Register a fill callback."""

    @abstractmethod
    def on_position_change(
        self,
        callback: Callable[[PositionState], Awaitable[None]],
    ) -> None:
        """Register a position callback."""

    async def _record_intent(self, intent: ExecutionIntent) -> None:
        await self._sink.write_intent(intent)

    async def _record_report(self, report: ExecutionReport) -> None:
        await self._sink.write_report(report)

    async def _record_fill(self, fill: FillRecord) -> None:
        await self._sink.write_fill(fill)

    async def _record_position(self, position: PositionState) -> None:
        await self._sink.write_position(position)


class ExecutionRouter(ABC):
    """Route intents to an execution engine."""

    @abstractmethod
    async def route(self, intent: ExecutionIntent) -> ExecutionEngine:
        """Resolve the engine that should handle the intent."""

    @abstractmethod
    def register_engine(
        self,
        venue: str,
        engine: ExecutionEngine,
        priority: int = 0,
    ) -> None:
        """Register an execution engine for a venue."""

    @abstractmethod
    def get_default_engine(self) -> ExecutionEngine:
        """Return the default engine."""


class ExecutionConfig(BaseModel):
    """Runtime config for the execution layer."""

    mode: ExecutionMode = ExecutionMode.SIMULATION
    backtest_start: Optional[datetime] = None
    backtest_end: Optional[datetime] = None
    initial_capital: Decimal = Decimal("100000")
    venue: Optional[str] = None
    account_id: Optional[str] = None
    enable_pre_trade_check: bool = True
    enable_post_trade_audit: bool = True
    max_order_size: Optional[Decimal] = None
    max_position_size: Optional[Decimal] = None
