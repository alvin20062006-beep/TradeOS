"""Execution event sinks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.execution.models import ExecutionIntent, ExecutionReport, FillRecord, PositionState


class ExecutionEventSink(ABC):
    @abstractmethod
    async def write_intent(self, intent: ExecutionIntent) -> None:
        """Persist one execution intent."""

    @abstractmethod
    async def write_report(self, report: ExecutionReport) -> None:
        """Persist one execution report."""

    @abstractmethod
    async def write_fill(self, fill: FillRecord) -> None:
        """Persist one fill."""

    @abstractmethod
    async def write_position(self, position: PositionState) -> None:
        """Persist one position snapshot."""

    async def flush(self) -> None:
        return None

    async def close(self) -> None:
        return None


class MemoryEventSink(ExecutionEventSink):
    """In-memory sink used by tests and simulation."""

    def __init__(self) -> None:
        self.intents: list[ExecutionIntent] = []
        self.reports: list[ExecutionReport] = []
        self.fills: list[FillRecord] = []
        self.positions: list[PositionState] = []
        self._closed = False

    async def write_intent(self, intent: ExecutionIntent) -> None:
        self._ensure_open()
        self.intents.append(intent)

    async def write_report(self, report: ExecutionReport) -> None:
        self._ensure_open()
        self.reports.append(report)

    async def write_fill(self, fill: FillRecord) -> None:
        self._ensure_open()
        self.fills.append(fill)

    async def write_position(self, position: PositionState) -> None:
        self._ensure_open()
        self.positions.append(position)

    def get_intents_for_strategy(self, strategy_id: str) -> list[ExecutionIntent]:
        return [intent for intent in self.intents if intent.strategy_id == strategy_id]

    def get_reports_for_intent(self, intent_id: str) -> list[ExecutionReport]:
        return [report for report in self.reports if report.intent_id == intent_id]

    def get_fills_for_order(self, order_id: str) -> list[FillRecord]:
        return [fill for fill in self.fills if fill.order_id == order_id]

    def get_position_for_symbol(self, symbol: str) -> Optional[PositionState]:
        positions = [position for position in self.positions if position.symbol == symbol]
        return max(positions, key=lambda item: item.updated_at) if positions else None

    def clear(self) -> None:
        self.intents.clear()
        self.reports.clear()
        self.fills.clear()
        self.positions.clear()

    async def close(self) -> None:
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Sink is closed")


class StubEventSink(ExecutionEventSink):
    """Explicit no-op sink for isolated tests."""

    async def write_intent(self, intent: ExecutionIntent) -> None:
        return None

    async def write_report(self, report: ExecutionReport) -> None:
        return None

    async def write_fill(self, fill: FillRecord) -> None:
        return None

    async def write_position(self, position: PositionState) -> None:
        return None


class CompositeEventSink(ExecutionEventSink):
    """Fan out events to multiple sinks."""

    def __init__(self, sinks: list[ExecutionEventSink]) -> None:
        self.sinks = sinks

    async def write_intent(self, intent: ExecutionIntent) -> None:
        for sink in self.sinks:
            await sink.write_intent(intent)

    async def write_report(self, report: ExecutionReport) -> None:
        for sink in self.sinks:
            await sink.write_report(report)

    async def write_fill(self, fill: FillRecord) -> None:
        for sink in self.sinks:
            await sink.write_fill(fill)

    async def write_position(self, position: PositionState) -> None:
        for sink in self.sinks:
            await sink.write_position(position)

    async def flush(self) -> None:
        for sink in self.sinks:
            await sink.flush()

    async def close(self) -> None:
        for sink in self.sinks:
            await sink.close()


class DatabaseEventSink(ExecutionEventSink):
    """Local JSONL-backed persistence sink used as a durable fallback."""

    def __init__(self, connection_string: Optional[str] = None) -> None:
        self.connection_string = connection_string
        self._initialized = False
        self._base = Path(connection_string) if connection_string else Path.home() / ".ai-trading-tool" / "execution_sink"
        self._base.mkdir(parents=True, exist_ok=True)

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            self._initialized = True

    async def write_intent(self, intent: ExecutionIntent) -> None:
        await self._ensure_initialized()
        self._append("intent", intent.model_dump_json())

    async def write_report(self, report: ExecutionReport) -> None:
        await self._ensure_initialized()
        self._append("report", report.model_dump_json())

    async def write_fill(self, fill: FillRecord) -> None:
        await self._ensure_initialized()
        self._append("fill", fill.model_dump_json())

    async def write_position(self, position: PositionState) -> None:
        await self._ensure_initialized()
        self._append("position", position.model_dump_json())

    def _append(self, category: str, payload: str) -> None:
        path = self._base / f"{category}-{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
