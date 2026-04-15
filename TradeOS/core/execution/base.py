"""
Execution Base - 执行层抽象接口

定义 ExecutionEngine 抽象基类，与具体实现（NautilusTrader）解耦。
所有业务逻辑通过此接口访问执行层，不直接依赖 Nautilus 内部对象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional, Callable, Awaitable

from pydantic import BaseModel

from ai_trading_tool.core.execution.enums import ExecutionMode
from ai_trading_tool.core.execution.models import (
    ExecutionIntent,
    ExecutionReport,
    PositionState,
    OrderRecord,
    FillRecord,
)
from ai_trading_tool.core.execution.sinks import ExecutionEventSink


# ─────────────────────────────────────────────────────────────
# 执行引擎抽象基类
# ─────────────────────────────────────────────────────────────

class ExecutionEngine(ABC):
    """执行引擎抽象基类
    
    本项目所有执行操作的统一入口。
    具体实现（如 NautilusAdapter）继承此类。
    
    职责：
    - 接收 ExecutionIntent，转换为底层订单
    - 返回 ExecutionReport，反馈执行状态
    - 提供仓位查询接口
    - 管理执行事件输出（sink）
    
    不承载：
    - 策略逻辑
    - 风控逻辑（风控层在 intent 到达前处理）
    - 决策仲裁（决策层生成 intent）
    """
    
    def __init__(
        self,
        mode: ExecutionMode,
        sink: ExecutionEventSink,
    ):
        self._mode = mode
        self._sink = sink
        self._running = False
    
    @property
    def mode(self) -> ExecutionMode:
        """执行模式"""
        return self._mode
    
    @property
    def is_running(self) -> bool:
        """是否运行中"""
        return self._running
    
    # ─────────────────────────────────────────────────────────
    # 生命周期管理
    # ─────────────────────────────────────────────────────────
    
    @abstractmethod
    async def start(self) -> None:
        """启动执行引擎
        
        根据 mode 初始化相应环境：
        - BACKTEST: 加载历史数据，准备回测环境
        - PAPER: 连接模拟交易所
        - LIVE: 连接真实交易所（受保护开关）
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止执行引擎
        
        优雅关闭：
        - 取消未完成订单
        - 刷新 sink
        - 释放资源
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
    
    # ─────────────────────────────────────────────────────────
    # 核心执行接口
    # ─────────────────────────────────────────────────────────
    
    @abstractmethod
    async def submit_intent(
        self,
        intent: ExecutionIntent,
    ) -> ExecutionReport:
        """提交执行意图
        
        主入口：决策层调用此方法提交交易意图。
        返回 ExecutionReport 表示已接受处理（不代表已成交）。
        
        Args:
            intent: 执行意图
            
        Returns:
            ExecutionReport: 初始执行报告（status=PENDING/SUBMITTED）
        """
        pass
    
    @abstractmethod
    async def cancel_order(
        self,
        order_id: str,
        reason: Optional[str] = None,
    ) -> ExecutionReport:
        """取消订单"""
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        new_quantity: Optional[Decimal] = None,
        new_price: Optional[Decimal] = None,
    ) -> ExecutionReport:
        """修改订单"""
        pass
    
    # ─────────────────────────────────────────────────────────
    # 状态查询接口
    # ─────────────────────────────────────────────────────────
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[OrderRecord]:
        """查询订单记录"""
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[PositionState]:
        """查询仓位状态"""
        pass
    
    @abstractmethod
    async def get_all_positions(self) -> list[PositionState]:
        """查询所有仓位"""
        pass
    
    @abstractmethod
    async def get_fills_for_order(
        self,
        order_id: str,
    ) -> list[FillRecord]:
        """查询订单的成交记录"""
        pass
    
    # ─────────────────────────────────────────────────────────
    # 事件订阅接口
    # ─────────────────────────────────────────────────────────
    
    @abstractmethod
    def on_fill(
        self,
        callback: Callable[[FillRecord], Awaitable[None]],
    ) -> None:
        """注册成交事件回调"""
        pass
    
    @abstractmethod
    def on_position_change(
        self,
        callback: Callable[[PositionState], Awaitable[None]],
    ) -> None:
        """注册仓位变化回调"""
        pass
    
    # ─────────────────────────────────────────────────────────
    # 内部辅助方法
    # ─────────────────────────────────────────────────────────
    
    async def _record_intent(self, intent: ExecutionIntent) -> None:
        """记录意图到 sink"""
        await self._sink.write_intent(intent)
    
    async def _record_report(self, report: ExecutionReport) -> None:
        """记录报告到 sink"""
        await self._sink.write_report(report)
    
    async def _record_fill(self, fill: FillRecord) -> None:
        """记录成交到 sink"""
        await self._sink.write_fill(fill)
    
    async def _record_position(self, position: PositionState) -> None:
        """记录仓位到 sink"""
        await self._sink.write_position(position)


# ─────────────────────────────────────────────────────────────
# 执行路由器抽象基类
# ─────────────────────────────────────────────────────────────

class ExecutionRouter(ABC):
    """执行路由器
    
    将 ExecutionIntent 路由到合适的 ExecutionEngine。
    
    当前阶段：所有路由到 Nautilus
    未来扩展：
    - 根据 venue 选择不同引擎
    - 根据 symbol 选择不同引擎
    - 根据策略类型选择不同引擎
    - 多 venue / 多 execution backend 支持
    """
    
    @abstractmethod
    async def route(self, intent: ExecutionIntent) -> ExecutionEngine:
        """根据意图选择执行引擎
        
        Args:
            intent: 执行意图
            
        Returns:
            ExecutionEngine: 选定的执行引擎
        """
        pass
    
    @abstractmethod
    def register_engine(
        self,
        venue: str,
        engine: ExecutionEngine,
        priority: int = 0,
    ) -> None:
        """注册执行引擎
        
        Args:
            venue: venue 标识，如 "NASDAQ", "BINANCE"
            engine: 执行引擎实例
            priority: 优先级（高优先级优先选择）
        """
        pass
    
    @abstractmethod
    def get_default_engine(self) -> ExecutionEngine:
        """获取默认引擎"""
        pass


# ─────────────────────────────────────────────────────────────
# 执行配置
# ─────────────────────────────────────────────────────────────

class ExecutionConfig(BaseModel):
    """执行层配置"""
    
    mode: ExecutionMode = ExecutionMode.BACKTEST
    
    # 回测配置
    backtest_start: Optional[datetime] = None
    backtest_end: Optional[datetime] = None
    initial_capital: Decimal = Decimal("100000")
    
    # 模拟/实盘配置
    venue: Optional[str] = None
    account_id: Optional[str] = None
    
    # 风控开关
    enable_pre_trade_check: bool = True
    enable_post_trade_audit: bool = True
    
    # 执行限制（预留，Phase 7 实现）
    max_order_size: Optional[Decimal] = None
    max_position_size: Optional[Decimal] = None
    max_daily_loss: Optional[Decimal] = None
    
    # 其他
    log_level: str = "INFO"
    event_sink_type: str = "memory"  # memory / stub / db


from datetime import datetime

from pydantic import BaseModel
