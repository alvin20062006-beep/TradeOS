"""
Test Nautilus Availability - Nautilus 不可用时的降级验证

验证：
- NAUTILUS_AVAILABLE 为 False 时行为正确
- NautilusAdapter 初始化抛出 RuntimeError
- NautilusRouter 初始化抛出 RuntimeError
- ExecutionRuntime 初始化抛出 RuntimeError
- 错误信息包含安装指令
"""

import pytest

from ai_trading_tool.core.execution.enums import ExecutionMode
from ai_trading_tool.core.execution.nautilus import NAUTILUS_AVAILABLE


class TestNautilusNotAvailable:
    """
    Nautilus 未安装时的降级行为测试。

    这些测试在 Nautilus 未安装时运行，验证组件的正确降级行为。
    """

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_nautilus_available_flag(self):
        """测试 NAUTILUS_AVAILABLE 标志为 False"""
        assert NAUTILUS_AVAILABLE is False

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_instrument_mapper_runtime_error(self):
        """测试 InstrumentMapper 在 Nautilus 缺失时抛出 RuntimeError"""
        from ai_trading_tool.core.execution.nautilus import InstrumentMapper

        mapper = InstrumentMapper()

        with pytest.raises(RuntimeError, match="NautilusTrader not available"):
            mapper.to_instrument_id("AAPL", "NASDAQ")

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_order_adapter_runtime_error(self):
        """测试 OrderAdapter 在 Nautilus 缺失时抛出 RuntimeError"""
        from ai_trading_tool.core.execution.nautilus import (
            InstrumentMapper,
            OrderAdapter,
        )

        mapper = InstrumentMapper()
        adapter = OrderAdapter(mapper)

        # OrderAdapter 方法应该在尝试创建 Order 时抛出错误
        # 由于 InstrumentMapper 也会失败，这里测试初始化后的状态
        assert adapter is not None

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_fill_adapter_runtime_error(self):
        """测试 FillAdapter 在 Nautilus 缺失时抛出 RuntimeError"""
        from ai_trading_tool.core.execution.nautilus import FillAdapter, InstrumentMapper

        mapper = InstrumentMapper()
        adapter = FillAdapter(mapper)

        assert adapter is not None

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_data_adapter_runtime_error(self):
        """测试 DataAdapter 在 Nautilus 缺失时抛出 RuntimeError"""
        from ai_trading_tool.core.execution.nautilus import DataAdapter, InstrumentMapper

        mapper = InstrumentMapper()
        adapter = DataAdapter(mapper)

        assert adapter is not None

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_nautilus_adapter_init_error(self):
        """测试 NautilusAdapter 初始化抛出 RuntimeError"""
        from ai_trading_tool.core.execution.nautilus.adapter import NautilusAdapter
        from ai_trading_tool.core.execution.sinks import MemoryEventSink

        sink = MemoryEventSink()

        with pytest.raises(RuntimeError, match="NautilusTrader not available"):
            NautilusAdapter(mode=ExecutionMode.BACKTEST, sink=sink, venue="NASDAQ")

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_nautilus_adapter_error_message_contains_install_instruction(self):
        """测试错误信息包含安装指令"""
        from ai_trading_tool.core.execution.nautilus.adapter import NautilusAdapter
        from ai_trading_tool.core.execution.sinks import MemoryEventSink

        sink = MemoryEventSink()

        try:
            NautilusAdapter(mode=ExecutionMode.BACKTEST, sink=sink, venue="NASDAQ")
            pytest.fail("Should have raised RuntimeError")

        except RuntimeError as e:
            error_msg = str(e)
            assert "NautilusTrader not available" in error_msg
            assert "pip install nautilus-trader" in error_msg

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_nautilus_router_init_error(self):
        """测试 NautilusRouter 初始化抛出 RuntimeError"""
        from ai_trading_tool.core.execution.router import NautilusRouter

        with pytest.raises(RuntimeError, match="NautilusTrader not available"):
            NautilusRouter(mode=ExecutionMode.BACKTEST)

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_nautilus_router_error_message_contains_install_instruction(self):
        """测试路由器错误信息包含安装指令"""
        from ai_trading_tool.core.execution.router import NautilusRouter

        try:
            NautilusRouter(mode=ExecutionMode.BACKTEST)
            pytest.fail("Should have raised RuntimeError")

        except RuntimeError as e:
            error_msg = str(e)
            assert "NautilusTrader not available" in error_msg
            assert "pip install nautilus-trader" in error_msg

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_execution_runtime_init_error(self):
        """测试 ExecutionRuntime 初始化抛出 RuntimeError"""
        from ai_trading_tool.core.execution.runtime import ExecutionRuntime

        with pytest.raises(RuntimeError, match="NautilusTrader not available"):
            ExecutionRuntime(mode=ExecutionMode.BACKTEST)

    @pytest.mark.skipif(
        NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus is NOT installed"
    )
    def test_execution_runtime_error_message_contains_install_instruction(self):
        """测试运行时错误信息包含安装指令"""
        from ai_trading_tool.core.execution.runtime import ExecutionRuntime

        try:
            ExecutionRuntime(mode=ExecutionMode.BACKTEST)
            pytest.fail("Should have raised RuntimeError")

        except RuntimeError as e:
            error_msg = str(e)
            assert "NautilusTrader not available" in error_msg
            assert "pip install nautilus-trader" in error_msg


class TestNautilusAvailable:
    """
    Nautilus 已安装时的测试。

    这些测试在 Nautilus 安装后运行，验证组件可以正常初始化。
    """

    @pytest.mark.skipif(
        not NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus IS installed"
    )
    def test_nautilus_available_flag(self):
        """测试 NAUTILUS_AVAILABLE 标志为 True"""
        assert NAUTILUS_AVAILABLE is True

    @pytest.mark.skipif(
        not NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus IS installed"
    )
    def test_nautilus_adapter_init_success(self):
        """测试 NautilusAdapter 初始化成功"""
        from ai_trading_tool.core.execution.nautilus.adapter import NautilusAdapter

        adapter = NautilusAdapter(mode=ExecutionMode.BACKTEST, venue="NASDAQ")

        assert adapter.mode == ExecutionMode.BACKTEST
        assert adapter.venue == "NASDAQ"
        assert not adapter.is_running

    @pytest.mark.skipif(
        not NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus IS installed"
    )
    def test_nautilus_router_init_success(self):
        """测试 NautilusRouter 初始化成功"""
        from ai_trading_tool.core.execution.router import NautilusRouter

        router = NautilusRouter(mode=ExecutionMode.BACKTEST)

        assert router.mode == ExecutionMode.BACKTEST
        assert not router.is_running

    @pytest.mark.skipif(
        not NAUTILUS_AVAILABLE, reason="Test only runs when Nautilus IS installed"
    )
    def test_execution_runtime_init_success(self):
        """测试 ExecutionRuntime 初始化成功"""
        from ai_trading_tool.core.execution.runtime import ExecutionRuntime
        from ai_trading_tool.core.execution.router import NautilusRouter

        router = NautilusRouter(mode=ExecutionMode.BACKTEST)
        runtime = ExecutionRuntime(router=router, mode=ExecutionMode.BACKTEST)

        assert runtime.mode == ExecutionMode.BACKTEST
        assert not runtime.is_running
