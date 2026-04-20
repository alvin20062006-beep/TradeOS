"""Local simulation execution engine."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Awaitable, Callable, Optional
from uuid import uuid4

from core.execution.base import ExecutionEngine
from core.execution.enums import (
    EngineStatus,
    ExecutionMode,
    ExecutionStatus,
    LiquiditySide,
    OrderType,
    Side,
)
from core.execution.models import (
    ExecutionIntent,
    ExecutionReport,
    FillRecord,
    OrderRecord,
    PositionState,
)
from core.execution.sinks import ExecutionEventSink, MemoryEventSink


class SimulationExecutionEngine(ExecutionEngine):
    """Runnable local execution engine used for simulation/paper fallback."""

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SIMULATION,
        *,
        sink: Optional[ExecutionEventSink] = None,
        venue: str = "SIMULATED",
    ) -> None:
        super().__init__(mode=mode, sink=sink or MemoryEventSink())
        self._venue = venue
        self._orders: dict[str, OrderRecord] = {}
        self._fills: dict[str, list[FillRecord]] = {}
        self._positions: dict[str, PositionState] = {}
        self._fill_callbacks: list[Callable[[FillRecord], Awaitable[None]]] = []
        self._position_callbacks: list[Callable[[PositionState], Awaitable[None]]] = []
        self._engine_status = EngineStatus.STOPPED

    @property
    def venue(self) -> str:
        return self._venue

    async def start(self) -> None:
        if self._running:
            return
        self._engine_status = EngineStatus.STARTING
        self._running = True
        self._engine_status = EngineStatus.RUNNING

    async def stop(self) -> None:
        if not self._running:
            return
        self._engine_status = EngineStatus.STOPPING
        self._running = False
        self._engine_status = EngineStatus.STOPPED

    async def health_check(self) -> bool:
        return self._running and self._engine_status == EngineStatus.RUNNING

    async def submit_intent(self, intent: ExecutionIntent) -> ExecutionReport:
        if not self._running:
            raise RuntimeError("Engine not running")
        if intent.quantity <= 0:
            raise ValueError("ExecutionIntent quantity must be positive")
        if intent.has_blocking_risk():
            raise RuntimeError("ExecutionIntent contains blocking risk flags")

        await self._record_intent(intent)

        order_id = f"sim-ord-{uuid4().hex[:12]}"
        order = OrderRecord(
            intent_id=intent.intent_id,
            order_id=order_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            quantity=intent.quantity,
            price=intent.price,
            stop_price=intent.stop_price,
            time_in_force=intent.time_in_force,
            current_status=ExecutionStatus.SUBMITTED,
        )
        self._orders[order_id] = order

        fill = self._build_fill(intent=intent, order_id=order_id)
        self._fills[order_id] = [fill]
        order.fills.append(fill.record_id)
        order.add_transition(ExecutionStatus.ACKNOWLEDGED, reason="simulation_ack")
        order.add_transition(ExecutionStatus.FILLED, reason=f"{self.mode.value.lower()}_fill")

        position = self._update_position(intent=intent, order_id=order_id, fill=fill)
        report = ExecutionReport(
            intent_id=intent.intent_id,
            order_id=order_id,
            status=ExecutionStatus.FILLED,
            submitted_at=datetime.utcnow(),
            acknowledged_at=datetime.utcnow(),
            filled_qty=fill.filled_qty,
            remaining_qty=Decimal("0"),
            avg_fill_price=fill.fill_price,
            total_fees=fill.fees,
            venue=self._venue,
            metadata={
                "engine": "simulation",
                "mode": self.mode.value,
                "slippage_bps": float(fill.metadata.get("simulated_slippage_bps", 0.0)),
            },
        )

        await self._record_fill(fill)
        await self._record_position(position)
        await self._record_report(report)

        for callback in self._fill_callbacks:
            await callback(fill)
        for callback in self._position_callbacks:
            await callback(position)

        return report

    async def cancel_order(self, order_id: str, reason: Optional[str] = None) -> ExecutionReport:
        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")
        order = self._orders[order_id]
        if order.current_status == ExecutionStatus.FILLED:
            raise RuntimeError("Filled simulation order cannot be cancelled")
        order.add_transition(ExecutionStatus.CANCELLED, reason=reason)
        report = ExecutionReport(
            intent_id=order.intent_id,
            order_id=order.order_id,
            status=ExecutionStatus.CANCELLED,
            last_update_at=datetime.utcnow(),
            venue=self._venue,
        )
        await self._record_report(report)
        return report

    async def modify_order(
        self,
        order_id: str,
        new_quantity: Optional[Decimal] = None,
        new_price: Optional[Decimal] = None,
    ) -> ExecutionReport:
        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")
        order = self._orders[order_id]
        if order.current_status == ExecutionStatus.FILLED:
            raise RuntimeError("Filled simulation order cannot be modified")
        if new_quantity is not None:
            order.quantity = new_quantity
        if new_price is not None:
            order.price = new_price
        report = ExecutionReport(
            intent_id=order.intent_id,
            order_id=order.order_id,
            status=order.current_status,
            last_update_at=datetime.utcnow(),
            venue=self._venue,
        )
        await self._record_report(report)
        return report

    async def get_order(self, order_id: str) -> Optional[OrderRecord]:
        return self._orders.get(order_id)

    async def get_position(self, symbol: str) -> Optional[PositionState]:
        return self._positions.get(symbol)

    async def get_all_positions(self) -> list[PositionState]:
        return list(self._positions.values())

    async def get_fills_for_order(self, order_id: str) -> list[FillRecord]:
        return list(self._fills.get(order_id, []))

    def on_fill(self, callback: Callable[[FillRecord], Awaitable[None]]) -> None:
        self._fill_callbacks.append(callback)

    def on_position_change(
        self,
        callback: Callable[[PositionState], Awaitable[None]],
    ) -> None:
        self._position_callbacks.append(callback)

    def _build_fill(self, *, intent: ExecutionIntent, order_id: str) -> FillRecord:
        arrival_price = intent.price or Decimal(str(intent.metadata.get("arrival_price", intent.metadata.get("reference_price", "100"))))
        estimated_slippage_bps = Decimal(str(intent.metadata.get("estimated_slippage_bps", 1.0)))
        fee_bps = Decimal(str(intent.metadata.get("fee_bps", 1.0)))
        price_multiplier = Decimal("1") + (
            estimated_slippage_bps / Decimal("10000")
            if intent.side == Side.BUY
            else -(estimated_slippage_bps / Decimal("10000"))
        )
        fill_price = (arrival_price * price_multiplier).quantize(Decimal("0.0001"))
        fees = (fill_price * intent.quantity * fee_bps / Decimal("10000")).quantize(Decimal("0.0001"))
        return FillRecord(
            order_id=order_id,
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            filled_qty=intent.quantity,
            fill_price=fill_price,
            fees=fees,
            venue=self._venue,
            trade_id=f"sim-fill-{uuid4().hex[:12]}",
            liquidity_side=LiquiditySide.TAKER if intent.order_type == OrderType.MARKET else LiquiditySide.MAKER,
            filled_at=datetime.utcnow(),
            metadata={
                "arrival_price": str(arrival_price),
                "simulated_slippage_bps": float(estimated_slippage_bps),
            },
        )

    def _update_position(
        self,
        *,
        intent: ExecutionIntent,
        order_id: str,
        fill: FillRecord,
    ) -> PositionState:
        position = self._positions.get(intent.symbol) or PositionState(symbol=intent.symbol, venue=self._venue)
        signed_qty = fill.filled_qty if intent.side == Side.BUY else -fill.filled_qty
        previous_qty = position.net_qty
        new_qty = previous_qty + signed_qty
        if new_qty != 0:
            weighted_cost = (position.avg_cost * abs(previous_qty)) + (fill.fill_price * fill.filled_qty)
            position.avg_cost = (weighted_cost / (abs(previous_qty) + fill.filled_qty)).quantize(Decimal("0.0001"))
        position.net_qty = new_qty
        position.total_traded_qty += fill.filled_qty
        position.total_fees += fill.fees
        position.exposure = abs(new_qty * fill.fill_price)
        position.updated_at = datetime.utcnow()
        if position.opened_at is None and new_qty != 0:
            position.opened_at = datetime.utcnow()
        position.source_orders.append(order_id)
        position.source_fills.append(fill.record_id)
        self._positions[intent.symbol] = position
        return position
