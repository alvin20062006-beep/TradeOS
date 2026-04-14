"""
Execution Event Sinks - 执行事件输出接口

Phase 3 重点：执行适配闭环，不是审计层全落地。

提供：
- ExecutionEventSink: 抽象接口
- MemoryEventSink: 内存实现（测试用）
- StubEventSink: 空实现（占位用）
- DatabaseEventSink: 数据库实现（预留，Phase 3 不强制）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ai_trading_tool.core.execution.models import (
    ExecutionIntent,
    ExecutionReport,
    FillRecord,
    PositionState,
)


class ExecutionEventSink(ABC):
    """执行事件输出接口
    
    所有执行事件（意图、报告、成交、仓位）通过此接口输出。
    实现可以是内存、数据库、消息队列等。
    """
    
    @abstractmethod
    async def write_intent(self, intent: ExecutionIntent) -> None:
        """记录执行意图"""
        pass
    
    @abstractmethod
    async def write_report(self, report: ExecutionReport) -> None:
        """记录执行报告"""
        pass
    
    @abstractmethod
    async def write_fill(self, fill: FillRecord) -> None:
        """记录成交"""
        pass
    
    @abstractmethod
    async def write_position(self, position: PositionState) -> None:
        """记录仓位状态"""
        pass
    
    async def flush(self) -> None:
        """刷新缓冲区（可选实现）"""
        pass
    
    async def close(self) -> None:
        """关闭连接（可选实现）"""
        pass


class MemoryEventSink(ExecutionEventSink):
    """内存事件输出 - 用于测试
    
    所有事件存储在内存列表中，便于测试验证。
    """
    
    def __init__(self):
        self.intents: list[ExecutionIntent] = []
        self.reports: list[ExecutionReport] = []
        self.fills: list[FillRecord] = []
        self.positions: list[PositionState] = []
        self._closed = False
    
    async def write_intent(self, intent: ExecutionIntent) -> None:
        if self._closed:
            raise RuntimeError("Sink is closed")
        self.intents.append(intent)
    
    async def write_report(self, report: ExecutionReport) -> None:
        if self._closed:
            raise RuntimeError("Sink is closed")
        self.reports.append(report)
    
    async def write_fill(self, fill: FillRecord) -> None:
        if self._closed:
            raise RuntimeError("Sink is closed")
        self.fills.append(fill)
    
    async def write_position(self, position: PositionState) -> None:
        if self._closed:
            raise RuntimeError("Sink is closed")
        self.positions.append(position)
    
    def get_intents_for_strategy(self, strategy_id: str) -> list[ExecutionIntent]:
        """获取指定策略的所有意图"""
        return [i for i in self.intents if i.strategy_id == strategy_id]
    
    def get_reports_for_intent(self, intent_id: str) -> list[ExecutionReport]:
        """获取指定意图的所有报告"""
        return [r for r in self.reports if r.intent_id == intent_id]
    
    def get_fills_for_order(self, order_id: str) -> list[FillRecord]:
        """获取指定订单的所有成交"""
        return [f for f in self.fills if f.order_id == order_id]
    
    def get_position_for_symbol(self, symbol: str) -> Optional[PositionState]:
        """获取指定标的的最新仓位"""
        positions = [p for p in self.positions if p.symbol == symbol]
        if not positions:
            return None
        # 返回最新的
        return max(positions, key=lambda p: p.updated_at)
    
    def clear(self) -> None:
        """清空所有记录"""
        self.intents.clear()
        self.reports.clear()
        self.fills.clear()
        self.positions.clear()
    
    async def close(self) -> None:
        self._closed = True


class StubEventSink(ExecutionEventSink):
    """空事件输出 - 用于占位
    
    不实际存储任何数据，仅作为接口占位。
    """
    
    async def write_intent(self, intent: ExecutionIntent) -> None:
        pass
    
    async def write_report(self, report: ExecutionReport) -> None:
        pass
    
    async def write_fill(self, fill: FillRecord) -> None:
        pass
    
    async def write_position(self, position: PositionState) -> None:
        pass


class CompositeEventSink(ExecutionEventSink):
    """组合事件输出
    
    将事件同时写入多个 sink，用于同时输出到内存和数据库等。
    """
    
    def __init__(self, sinks: list[ExecutionEventSink]):
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
    """数据库事件输出 - 预留接口
    
    Phase 3 不强制实现，仅预留接口。
    后续可接入 PostgreSQL 等持久化存储。
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string
        self._initialized = False
    
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            # 预留：初始化数据库连接
            # 后续实现：创建连接池、检查表结构等
            self._initialized = True
    
    async def write_intent(self, intent: ExecutionIntent) -> None:
        await self._ensure_initialized()
        # 预留：写入数据库
        raise NotImplementedError("Database sink not implemented in Phase 3")
    
    async def write_report(self, report: ExecutionReport) -> None:
        await self._ensure_initialized()
        raise NotImplementedError("Database sink not implemented in Phase 3")
    
    async def write_fill(self, fill: FillRecord) -> None:
        await self._ensure_initialized()
        raise NotImplementedError("Database sink not implemented in Phase 3")
    
    async def write_position(self, position: PositionState) -> None:
        await self._ensure_initialized()
        raise NotImplementedError("Database sink not implemented in Phase 3")
