"""
NautilusAdapter - NautilusTrader 执行引擎适配器

实现 ExecutionEngine 接口，封装 Nautilus 执行引擎。
支持 backtest/paper/live 三种模式。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, Awaitable, Optional

from ai_trading_tool.core.execution.base import ExecutionEngine
from ai_trading_tool.core.execution.enums import ExecutionMode, ExecutionStatus
from ai_trading_tool.core.execution.models import (
    EngineStatus,
    ExecutionIntent,
    ExecutionReport,
    FillRecord,
    OrderRecord,
    PositionState,
    OrderSnapshot,
)
from ai_trading_tool.core.execution.nautilus import (
    NAUTILUS_AVAILABLE,
    FillAdapter,
    InstrumentMapper,
    OrderAdapter,
)
from ai_trading_tool.core.execution.sinks import ExecutionEventSink, MemoryEventSink

if TYPE_CHECKING:
    from nautilus_trader.cache.cache import Cache
    from nautilus_trader.common.component import MessageBus
    from nautilus_trader.execution.client import ExecutionClient


class NautilusAdapter(ExecutionEngine):
    """
    NautilusTrader 执行引擎适配器。

    封装 Nautilus 执行引擎，提供统一的 ExecutionEngine 接口。
    支持 backtest/paper/live 三种模式。

    设计约束：
    - 业务逻辑不直接耦合 Nautilus 内部对象
    - Nautilus 不可用时，初始化抛出 RuntimeError
    - 所有方法都有明确的错误处理
    """

    def __init__(
        self,
        mode: ExecutionMode,
        sink: Optional[ExecutionEventSink] = None,
        venue: str = "DEFAULT",
        mapper: Optional[InstrumentMapper] = None,
    ):
        """
        初始化 NautilusAdapter。

        Args:
            mode: 执行模式（BACKTEST/PAPER/LIVE）
            sink: 事件输出 sink
            venue: 交易所/平台名称
            mapper: InstrumentMapper 实例（可选，自动创建）

        Raises:
            RuntimeError: NautilusTrader 未安装
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError(
                "NautilusTrader not available. "
                "Install with: pip install nautilus-trader"
            )

        super().__init__(mode=mode, sink=sink or MemoryEventSink())

        self._venue = venue
        self._mapper = mapper or InstrumentMapper()

        # 内部组件（延迟初始化）
        self._client: Optional[ExecutionClient] = None
        self._cache: Optional[Cache] = None
        self._msgbus: Optional[MessageBus] = None

        # 适配器
        self._order_adapter = OrderAdapter(self._mapper)
        self._fill_adapter = FillAdapter(self._mapper)

        # 订单追踪
        self._orders: dict[str, OrderRecord] = {}
        self._fills: dict[str, list[FillRecord]] = {}
        self._positions: dict[str, PositionState] = {}

        # 回调
        self._fill_callbacks: list[Callable[[FillRecord], Awaitable[None]]] = []
        self._position_callbacks: list[Callable[[PositionState], Awaitable[None]]] = []

        # 状态
        self._engine_status = EngineStatus.STOPPED

    # ==================== ExecutionEngine 接口实现 ====================

    async def start(self) -> None:
        """启动执行引擎"""
        if self._running:
            return

        self._engine_status = EngineStatus.STARTING

        try:
            # 初始化 Nautilus 组件（实际实现需要完整集成）
            # self._init_nautilus_components()

            self._running = True
            self._engine_status = EngineStatus.RUNNING

        except Exception as e:
            self._engine_status = EngineStatus.ERROR
            raise RuntimeError(f"Failed to start NautilusAdapter: {e}") from e

    async def stop(self) -> None:
        """停止执行引擎"""
        if not self._running:
            return

        self._engine_status = EngineStatus.STOPPING

        try:
            # 清理 Nautilus 组件
            # self._cleanup_nautilus_components()

            self._running = False
            self._engine_status = EngineStatus.STOPPED

        except Exception as e:
            self._engine_status = EngineStatus.ERROR
            raise RuntimeError(f"Failed to stop NautilusAdapter: {e}") from e

    async def health_check(self) -> bool:
        """健康检查"""
        return self._running and self._engine_status == EngineStatus.RUNNING

    async def submit_intent(self, intent: ExecutionIntent) -> ExecutionReport:
        """
        提交执行意图。

        Args:
            intent: 执行意图

        Returns:
            ExecutionReport: 初始执行报告
        """
        if not self._running:
            raise RuntimeError("Engine not running")

        # 验证 intent
        self._validate_intent(intent)

        # 记录意图
        await self._record_intent(intent)

        # 转换为 Nautilus Order
        order = self._order_adapter.adapt(intent)
        order_id = str(order.client_order_id)

        # 创建 OrderRecord
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

        # 提交到 Nautilus（实际实现）
        # if self._client:
        #     self._client.submit_order(order)

        # 创建初始报告
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
        """取消订单"""
        if not self._running:
            raise RuntimeError("Engine not running")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        record = self._orders[order_id]

        # 取消订单（实际实现）
        # if self._client:
        #     self._client.cancel_order(order_id)

        # 更新状态
        record.add_transition(ExecutionStatus.CANCELLED, reason=reason)

        # 创建报告
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
        """修改订单"""
        if not self._running:
            raise RuntimeError("Engine not running")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        record = self._orders[order_id]

        # 更新数量/价格
        if new_quantity:
            record.quantity = new_quantity
        if new_price:
            record.price = new_price

        # 修改订单（实际实现）
        # if self._client:
        #     self._client.modify_order(order_id, ...)

        # 创建报告
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
        """查询订单记录"""
        return self._orders.get(order_id)

    async def get_position(self, symbol: str) -> Optional[PositionState]:
        """查询仓位状态"""
        return self._positions.get(symbol)

    async def get_all_positions(self) -> list[PositionState]:
        """查询所有仓位"""
        return list(self._positions.values())

    async def get_fills_for_order(self, order_id: str) -> list[FillRecord]:
        """查询订单的成交记录"""
        return self._fills.get(order_id, [])

    def on_fill(self, callback: Callable[[FillRecord], Awaitable[None]]) -> None:
        """注册成交事件回调"""
        self._fill_callbacks.append(callback)

    def on_position_change(
        self,
        callback: Callable[[PositionState], Awaitable[None]],
    ) -> None:
        """注册仓位变化回调"""
        self._position_callbacks.append(callback)

    # ==================== 内部方法 ====================

    def _validate_intent(self, intent: ExecutionIntent) -> None:
        """验证执行意图"""
        if not intent.symbol:
            raise ValueError("ExecutionIntent must have a symbol")

        if intent.quantity <= 0:
            raise ValueError("ExecutionIntent quantity must be positive")

    async def _process_fill(self, event) -> None:
        """
        处理成交事件（内部）。

        Args:
            event: Nautilus OrderFilled 事件
        """
        order_id = str(event.client_order_id)

        if order_id not in self._orders:
            return

        record = self._orders[order_id]

        # 转换成交记录
        fill = self._fill_adapter.adapt(event, intent_id=record.intent_id)

        # 追踪成交
        if order_id not in self._fills:
            self._fills[order_id] = []
        self._fills[order_id].append(fill)

        # 更新订单状态
        record.add_transition(ExecutionStatus.FILLED)

        # 记录成交
        await self._record_fill(fill)

        # 触发回调
        for callback in self._fill_callbacks:
            await callback(fill)

    # ==================== 属性访问器 ====================

    @property
    def venue(self) -> str:
        """交易所"""
        return self._venue
