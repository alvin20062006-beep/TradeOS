"""
NautilusAdapter - NautilusTrader ???????????????
?????ExecutionEngine ???????????Nautilus ???????????????? backtest/paper/live ???????????"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, Awaitable, Optional

from core.execution.base import ExecutionEngine
from core.execution.enums import ExecutionMode, ExecutionStatus
from core.execution.models import (
    EngineStatus,
    ExecutionIntent,
    ExecutionReport,
    FillRecord,
    OrderRecord,
    PositionState,
    OrderSnapshot,
)
from core.execution.nautilus import (
    NAUTILUS_AVAILABLE,
    FillAdapter,
    InstrumentMapper,
    OrderAdapter,
)
from core.execution.sinks import ExecutionEventSink, MemoryEventSink

if TYPE_CHECKING:
    from nautilus_trader.cache.cache import Cache
    from nautilus_trader.common.component import MessageBus
    from nautilus_trader.execution.client import ExecutionClient


class NautilusAdapter(ExecutionEngine):
    """
    NautilusTrader ??????????????????
    ?????Nautilus ???????????????????????ExecutionEngine ???????    ????? backtest/paper/live ???????????
    ???????????    - ??????????????????????Nautilus ??????????
    - Nautilus ???????????????????????RuntimeError
    - ??????????????????????????????
    """

    def __init__(
        self,
        mode: ExecutionMode,
        sink: Optional[ExecutionEventSink] = None,
        venue: str = "DEFAULT",
        mapper: Optional[InstrumentMapper] = None,
    ):
        """
        ???????NautilusAdapter??
        Args:
            mode: ????????????ACKTEST/PAPER/LIVE??            sink: ????????? sink
            venue: ?????????????????
            mapper: InstrumentMapper ?????????????????????????
        Raises:
            RuntimeError: NautilusTrader ???????        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError(
                "NautilusTrader not available. "
                "Install with: pip install nautilus-trader"
            )

        super().__init__(mode=mode, sink=sink or MemoryEventSink())

        self._venue = venue
        self._mapper = mapper or InstrumentMapper()

        # ?????????????????????????        self._client: Optional[ExecutionClient] = None
        self._cache: Optional[Cache] = None
        self._msgbus: Optional[MessageBus] = None

        # ???????        self._order_adapter = OrderAdapter(self._mapper)
        self._fill_adapter = FillAdapter(self._mapper)

        # ?????????
        self._orders: dict[str, OrderRecord] = {}
        self._fills: dict[str, list[FillRecord]] = {}
        self._positions: dict[str, PositionState] = {}

        # ?????
        self._fill_callbacks: list[Callable[[FillRecord], Awaitable[None]]] = []
        self._position_callbacks: list[Callable[[PositionState], Awaitable[None]]] = []

        # ?????        self._engine_status = EngineStatus.STOPPED

    # ==================== ExecutionEngine ??????????====================

    async def start(self) -> None:
        """?????????????"""
        if self._running:
            return

        self._engine_status = EngineStatus.STARTING

        try:
            # ???????Nautilus ????????????????????????????????
            # self._init_nautilus_components()

            self._running = True
            self._engine_status = EngineStatus.RUNNING

        except Exception as e:
            self._engine_status = EngineStatus.ERROR
            raise RuntimeError(f"Failed to start NautilusAdapter: {e}") from e

    async def stop(self) -> None:
        """?????????????"""
        if not self._running:
            return

        self._engine_status = EngineStatus.STOPPING

        try:
            # ?????Nautilus ?????
            # self._cleanup_nautilus_components()

            self._running = False
            self._engine_status = EngineStatus.STOPPED

        except Exception as e:
            self._engine_status = EngineStatus.ERROR
            raise RuntimeError(f"Failed to stop NautilusAdapter: {e}") from e

    async def health_check(self) -> bool:
        """??????????"""
        return self._running and self._engine_status == EngineStatus.RUNNING

    async def submit_intent(self, intent: ExecutionIntent) -> ExecutionReport:
        """
        ???????????????
        Args:
            intent: ?????????

        Returns:
            ExecutionReport: ?????????????
        """
        if not self._running:
            raise RuntimeError("Engine not running")

        # ?????intent
        self._validate_intent(intent)

        # ?????????
        await self._record_intent(intent)

        # ???????Nautilus Order
        order = self._order_adapter.adapt(intent)
        order_id = str(order.client_order_id)

        # ?????OrderRecord
        record = OrderRecord(
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
        self._orders[order_id] = record

        # ???????Nautilus??????????????
        # if self._client:
        #     self._client.submit_order(order)

        # ??????????????
        report = ExecutionReport(
            intent_id=intent.intent_id,
            order_id=order_id,
            status=ExecutionStatus.SUBMITTED,
            submitted_at=datetime.now(),
            venue=self._venue,
        )

        await self._record_report(report)

        return report

    async def cancel_order(
        self,
        order_id: str,
        reason: Optional[str] = None,
    ) -> ExecutionReport:
        """?????????"""
        if not self._running:
            raise RuntimeError("Engine not running")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        record = self._orders[order_id]

        # ???????????????????????
        # if self._client:
        #     self._client.cancel_order(order_id)

        # ??????????        record.add_transition(ExecutionStatus.CANCELLED, reason=reason)

        # ?????????
        report = ExecutionReport(
            intent_id=record.intent_id,
            order_id=order_id,
            status=ExecutionStatus.CANCELLED,
            last_update_at=datetime.now(),
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
        """?????????"""
        if not self._running:
            raise RuntimeError("Engine not running")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        record = self._orders[order_id]

        # ?????????/?????
        if new_quantity:
            record.quantity = new_quantity
        if new_price:
            record.price = new_price

        # ???????????????????????
        # if self._client:
        #     self._client.modify_order(order_id, ...)

        # ?????????
        report = ExecutionReport(
            intent_id=record.intent_id,
            order_id=order_id,
            status=record.current_status,
            last_update_at=datetime.now(),
            venue=self._venue,
        )

        await self._record_report(report)

        return report

    async def get_order(self, order_id: str) -> Optional[OrderRecord]:
        """??????????????"""
        return self._orders.get(order_id)

    async def get_position(self, symbol: str) -> Optional[PositionState]:
        """??????????????"""
        return self._positions.get(symbol)

    async def get_all_positions(self) -> list[PositionState]:
        """??????????????"""
        return list(self._positions.values())

    async def get_fills_for_order(self, order_id: str) -> list[FillRecord]:
        """????????????????????"""
        return self._fills.get(order_id, [])

    def on_fill(self, callback: Callable[[FillRecord], Awaitable[None]]) -> None:
        """??????????????????"""
        self._fill_callbacks.append(callback)

    def on_position_change(
        self,
        callback: Callable[[PositionState], Awaitable[None]],
    ) -> None:
        """??????????????????"""
        self._position_callbacks.append(callback)

    # ==================== ????????? ====================

    def _validate_intent(self, intent: ExecutionIntent) -> None:
        """?????????????"""
        if not intent.symbol:
            raise ValueError("ExecutionIntent must have a symbol")

        if intent.quantity <= 0:
            raise ValueError("ExecutionIntent quantity must be positive")

    async def _process_fill(self, event) -> None:
        """
        ?????????????????????????
        Args:
            event: Nautilus OrderFilled ?????
        """
        order_id = str(event.client_order_id)

        if order_id not in self._orders:
            return

        record = self._orders[order_id]

        # ??????????????
        fill = self._fill_adapter.adapt(event, intent_id=record.intent_id)

        # ??????????
        if order_id not in self._fills:
            self._fills[order_id] = []
        self._fills[order_id].append(fill)

        # ??????????????        record.add_transition(ExecutionStatus.FILLED)

        # ?????????
        await self._record_fill(fill)

        # ?????????
        for callback in self._fill_callbacks:
            await callback(fill)

    # ==================== ????????????====================

    @property
    def venue(self) -> str:
        """????????"""
        return self._venue

