"""
NautilusAdapter - NautilusTrader 鎵ц寮曟搸閫傞厤鍣?
瀹炵幇 ExecutionEngine 鎺ュ彛锛屽皝瑁?Nautilus 鎵ц寮曟搸銆?鏀寔 backtest/paper/live 涓夌妯″紡銆?"""

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
    NautilusTrader 鎵ц寮曟搸閫傞厤鍣ㄣ€?
    灏佽 Nautilus 鎵ц寮曟搸锛屾彁渚涚粺涓€鐨?ExecutionEngine 鎺ュ彛銆?    鏀寔 backtest/paper/live 涓夌妯″紡銆?
    璁捐绾︽潫锛?    - 涓氬姟閫昏緫涓嶇洿鎺ヨ€﹀悎 Nautilus 鍐呴儴瀵硅薄
    - Nautilus 涓嶅彲鐢ㄦ椂锛屽垵濮嬪寲鎶涘嚭 RuntimeError
    - 鎵€鏈夋柟娉曢兘鏈夋槑纭殑閿欒澶勭悊
    """

    def __init__(
        self,
        mode: ExecutionMode,
        sink: Optional[ExecutionEventSink] = None,
        venue: str = "DEFAULT",
        mapper: Optional[InstrumentMapper] = None,
    ):
        """
        鍒濆鍖?NautilusAdapter銆?
        Args:
            mode: 鎵ц妯″紡锛圔ACKTEST/PAPER/LIVE锛?            sink: 浜嬩欢杈撳嚭 sink
            venue: 浜ゆ槗鎵€/骞冲彴鍚嶇О
            mapper: InstrumentMapper 瀹炰緥锛堝彲閫夛紝鑷姩鍒涘缓锛?
        Raises:
            RuntimeError: NautilusTrader 鏈畨瑁?        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError(
                "NautilusTrader not available. "
                "Install with: pip install nautilus-trader"
            )

        super().__init__(mode=mode, sink=sink or MemoryEventSink())

        self._venue = venue
        self._mapper = mapper or InstrumentMapper()

        # 鍐呴儴缁勪欢锛堝欢杩熷垵濮嬪寲锛?        self._client: Optional[ExecutionClient] = None
        self._cache: Optional[Cache] = None
        self._msgbus: Optional[MessageBus] = None

        # 閫傞厤鍣?        self._order_adapter = OrderAdapter(self._mapper)
        self._fill_adapter = FillAdapter(self._mapper)

        # 璁㈠崟杩借釜
        self._orders: dict[str, OrderRecord] = {}
        self._fills: dict[str, list[FillRecord]] = {}
        self._positions: dict[str, PositionState] = {}

        # 鍥炶皟
        self._fill_callbacks: list[Callable[[FillRecord], Awaitable[None]]] = []
        self._position_callbacks: list[Callable[[PositionState], Awaitable[None]]] = []

        # 鐘舵€?        self._engine_status = EngineStatus.STOPPED

    # ==================== ExecutionEngine 鎺ュ彛瀹炵幇 ====================

    async def start(self) -> None:
        """鍚姩鎵ц寮曟搸"""
        if self._running:
            return

        self._engine_status = EngineStatus.STARTING

        try:
            # 鍒濆鍖?Nautilus 缁勪欢锛堝疄闄呭疄鐜伴渶瑕佸畬鏁撮泦鎴愶級
            # self._init_nautilus_components()

            self._running = True
            self._engine_status = EngineStatus.RUNNING

        except Exception as e:
            self._engine_status = EngineStatus.ERROR
            raise RuntimeError(f"Failed to start NautilusAdapter: {e}") from e

    async def stop(self) -> None:
        """鍋滄鎵ц寮曟搸"""
        if not self._running:
            return

        self._engine_status = EngineStatus.STOPPING

        try:
            # 娓呯悊 Nautilus 缁勪欢
            # self._cleanup_nautilus_components()

            self._running = False
            self._engine_status = EngineStatus.STOPPED

        except Exception as e:
            self._engine_status = EngineStatus.ERROR
            raise RuntimeError(f"Failed to stop NautilusAdapter: {e}") from e

    async def health_check(self) -> bool:
        """鍋ュ悍妫€鏌?""
        return self._running and self._engine_status == EngineStatus.RUNNING

    async def submit_intent(self, intent: ExecutionIntent) -> ExecutionReport:
        """
        鎻愪氦鎵ц鎰忓浘銆?
        Args:
            intent: 鎵ц鎰忓浘

        Returns:
            ExecutionReport: 鍒濆鎵ц鎶ュ憡
        """
        if not self._running:
            raise RuntimeError("Engine not running")

        # 楠岃瘉 intent
        self._validate_intent(intent)

        # 璁板綍鎰忓浘
        await self._record_intent(intent)

        # 杞崲涓?Nautilus Order
        order = self._order_adapter.adapt(intent)
        order_id = str(order.client_order_id)

        # 鍒涘缓 OrderRecord
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

        # 鎻愪氦鍒?Nautilus锛堝疄闄呭疄鐜帮級
        # if self._client:
        #     self._client.submit_order(order)

        # 鍒涘缓鍒濆鎶ュ憡
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
        """鍙栨秷璁㈠崟"""
        if not self._running:
            raise RuntimeError("Engine not running")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        record = self._orders[order_id]

        # 鍙栨秷璁㈠崟锛堝疄闄呭疄鐜帮級
        # if self._client:
        #     self._client.cancel_order(order_id)

        # 鏇存柊鐘舵€?        record.add_transition(ExecutionStatus.CANCELLED, reason=reason)

        # 鍒涘缓鎶ュ憡
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
        """淇敼璁㈠崟"""
        if not self._running:
            raise RuntimeError("Engine not running")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        record = self._orders[order_id]

        # 鏇存柊鏁伴噺/浠锋牸
        if new_quantity:
            record.quantity = new_quantity
        if new_price:
            record.price = new_price

        # 淇敼璁㈠崟锛堝疄闄呭疄鐜帮級
        # if self._client:
        #     self._client.modify_order(order_id, ...)

        # 鍒涘缓鎶ュ憡
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
        """鏌ヨ璁㈠崟璁板綍"""
        return self._orders.get(order_id)

    async def get_position(self, symbol: str) -> Optional[PositionState]:
        """鏌ヨ浠撲綅鐘舵€?""
        return self._positions.get(symbol)

    async def get_all_positions(self) -> list[PositionState]:
        """鏌ヨ鎵€鏈変粨浣?""
        return list(self._positions.values())

    async def get_fills_for_order(self, order_id: str) -> list[FillRecord]:
        """鏌ヨ璁㈠崟鐨勬垚浜よ褰?""
        return self._fills.get(order_id, [])

    def on_fill(self, callback: Callable[[FillRecord], Awaitable[None]]) -> None:
        """娉ㄥ唽鎴愪氦浜嬩欢鍥炶皟"""
        self._fill_callbacks.append(callback)

    def on_position_change(
        self,
        callback: Callable[[PositionState], Awaitable[None]],
    ) -> None:
        """娉ㄥ唽浠撲綅鍙樺寲鍥炶皟"""
        self._position_callbacks.append(callback)

    # ==================== 鍐呴儴鏂规硶 ====================

    def _validate_intent(self, intent: ExecutionIntent) -> None:
        """楠岃瘉鎵ц鎰忓浘"""
        if not intent.symbol:
            raise ValueError("ExecutionIntent must have a symbol")

        if intent.quantity <= 0:
            raise ValueError("ExecutionIntent quantity must be positive")

    async def _process_fill(self, event) -> None:
        """
        澶勭悊鎴愪氦浜嬩欢锛堝唴閮級銆?
        Args:
            event: Nautilus OrderFilled 浜嬩欢
        """
        order_id = str(event.client_order_id)

        if order_id not in self._orders:
            return

        record = self._orders[order_id]

        # 杞崲鎴愪氦璁板綍
        fill = self._fill_adapter.adapt(event, intent_id=record.intent_id)

        # 杩借釜鎴愪氦
        if order_id not in self._fills:
            self._fills[order_id] = []
        self._fills[order_id].append(fill)

        # 鏇存柊璁㈠崟鐘舵€?        record.add_transition(ExecutionStatus.FILLED)

        # 璁板綍鎴愪氦
        await self._record_fill(fill)

        # 瑙﹀彂鍥炶皟
        for callback in self._fill_callbacks:
            await callback(fill)

    # ==================== 灞炴€ц闂櫒 ====================

    @property
    def venue(self) -> str:
        """浜ゆ槗鎵€"""
        return self._venue

