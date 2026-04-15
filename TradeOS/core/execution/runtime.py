"""
ExecutionRuntime - 执行引擎运行时

管理执行引擎生命周期（start/stop/health）。
不承载策略/风控逻辑。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ai_trading_tool.core.execution.enums import ExecutionMode
from ai_trading_tool.core.execution.models import EngineStatus, RuntimeReport
from ai_trading_tool.core.execution.nautilus import NAUTILUS_AVAILABLE

if TYPE_CHECKING:
    from ai_trading_tool.core.execution.nautilus.adapter import NautilusAdapter
    from ai_trading_tool.core.execution.router import NautilusRouter


class ExecutionRuntime:
    """
    执行引擎运行时。

    管理执行引擎生命周期（start/stop/health）。
    不承载策略/风控逻辑。

    设计约束：
    - runtime 只做生命周期管理
    - Nautilus 不可用时，启动抛出 RuntimeError
    - 不静默失败
    """

    def __init__(
        self,
        router: Optional[NautilusRouter] = None,
        mode: ExecutionMode = ExecutionMode.BACKTEST,
    ):
        """
        初始化 ExecutionRuntime。

        Args:
            router: NautilusRouter 实例（可选）
            mode: 执行模式（默认 BACKTEST）

        Raises:
            RuntimeError: NautilusTrader 未安装
        """
        if not NAUTILUS_AVAILABLE:
            raise RuntimeError(
                "NautilusTrader not available. "
                "Install with: pip install nautilus-trader"
            )

        self._router = router
        self._mode = mode
        self._status = EngineStatus.STOPPED
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

    # ==================== 生命周期管理 ====================

    async def start(self) -> None:
        """
        启动运行时。

        Raises:
            RuntimeError: 启动失败或 router 未配置
        """
        if self._status == EngineStatus.RUNNING:
            return

        if not self._router:
            raise RuntimeError("No router configured. Call configure() first.")

        self._status = EngineStatus.STARTING

        try:
            await self._router.start()
            self._started_at = datetime.utcnow()
            self._status = EngineStatus.RUNNING

        except Exception as e:
            self._status = EngineStatus.ERROR
            raise RuntimeError(f"Failed to start ExecutionRuntime: {e}") from e

    async def stop(self) -> None:
        """
        停止运行时。

        Raises:
            RuntimeError: 停止失败
        """
        if self._status == EngineStatus.STOPPED:
            return

        self._status = EngineStatus.STOPPING

        try:
            if self._router:
                await self._router.stop()

            self._stopped_at = datetime.utcnow()
            self._status = EngineStatus.STOPPED

        except Exception as e:
            self._status = EngineStatus.ERROR
            raise RuntimeError(f"Failed to stop ExecutionRuntime: {e}") from e

    async def restart(self) -> None:
        """
        重启运行时。

        Raises:
            RuntimeError: 重启失败
        """
        await self.stop()
        await self.start()

    # ==================== 配置管理 ====================

    def configure(self, router: NautilusRouter) -> None:
        """
        配置路由器。

        Args:
            router: NautilusRouter 实例

        Raises:
            RuntimeError: 运行时正在运行
        """
        if self._status == EngineStatus.RUNNING:
            raise RuntimeError("Cannot configure while runtime is running")

        self._router = router

    def register_adapter(self, adapter: NautilusAdapter) -> None:
        """
        注册 adapter 到路由器。

        Args:
            adapter: NautilusAdapter 实例

        Raises:
            RuntimeError: 路由器未配置
        """
        if not self._router:
            raise RuntimeError("No router configured")

        self._router.register_adapter(adapter)

    # ==================== 健康检查 ====================

    def health_check(self) -> RuntimeReport:
        """
        执行健康检查。

        Returns:
            RuntimeReport 包含运行时状态信息
        """
        adapter_status = {}

        if self._router:
            for venue in self._router.list_adapters():
                adapter = self._router.get_adapter(venue)
                if adapter:
                    adapter_status[venue] = adapter.engine_status().value

        return RuntimeReport(
            status=self._status.value,
            mode=self._mode.value,
            started_at=self._started_at.isoformat() if self._started_at else None,
            stopped_at=self._stopped_at.isoformat() if self._stopped_at else None,
            adapters=adapter_status,
        )

    def is_healthy(self) -> bool:
        """
        检查运行时是否健康。

        Returns:
            是否健康
        """
        return self._status == EngineStatus.RUNNING

    # ==================== 状态查询 ====================

    def status(self) -> EngineStatus:
        """
        获取运行时状态。

        Returns:
            EngineStatus
        """
        return self._status

    def uptime_seconds(self) -> Optional[int]:
        """
        获取运行时长（秒）。

        Returns:
            运行时长（未启动返回 None）
        """
        if not self._started_at:
            return None

        if self._status == EngineStatus.STOPPED:
            if self._stopped_at:
                delta = self._stopped_at - self._started_at
                return int(delta.total_seconds())
            return None

        delta = datetime.utcnow() - self._started_at
        return int(delta.total_seconds())

    # ==================== 上下文管理器 ====================

    async def __aenter__(self) -> ExecutionRuntime:
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.stop()

    # ==================== 属性访问器 ====================

    @property
    def router(self) -> Optional[NautilusRouter]:
        """路由器"""
        return self._router

    @property
    def mode(self) -> ExecutionMode:
        """执行模式"""
        return self._mode

    @mode.setter
    def mode(self, value: ExecutionMode) -> None:
        """设置执行模式"""
        self._mode = value
        if self._router:
            self._router.mode = value

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._status == EngineStatus.RUNNING
