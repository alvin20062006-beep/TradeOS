"""Execution availability and fallback behavior."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from core.execution import ExecutionIntent, ExecutionRuntime
from core.execution.enums import ExecutionMode, OrderType, Side
from core.execution.nautilus import NAUTILUS_AVAILABLE
from core.execution.router import NautilusRouter, SimulationRouter, build_default_router


class TestWhenNautilusMissing:
    @pytest.mark.skipif(NAUTILUS_AVAILABLE, reason="Only relevant when Nautilus is absent")
    def test_live_router_raises(self) -> None:
        with pytest.raises(RuntimeError, match="NautilusTrader not available"):
            NautilusRouter(mode=ExecutionMode.LIVE)

    @pytest.mark.skipif(NAUTILUS_AVAILABLE, reason="Only relevant when Nautilus is absent")
    def test_live_runtime_raises(self) -> None:
        with pytest.raises(RuntimeError, match="NautilusTrader not available"):
            ExecutionRuntime(mode=ExecutionMode.LIVE)

    @pytest.mark.skipif(NAUTILUS_AVAILABLE, reason="Only relevant when Nautilus is absent")
    def test_simulation_runtime_executes(self) -> None:
        async def _run():
            runtime = ExecutionRuntime(mode=ExecutionMode.SIMULATION)
            await runtime.start()
            try:
                return await runtime.execute(
                    ExecutionIntent(
                        strategy_id="TEST",
                        decision_id="decision-1",
                        symbol="AAPL",
                        venue="SIMULATED",
                        side=Side.BUY,
                        order_type=OrderType.MARKET,
                        quantity=Decimal("10"),
                        metadata={"reference_price": 100.0, "estimated_slippage_bps": 2.0},
                    )
                )
            finally:
                await runtime.stop()

        result = asyncio.run(_run())
        assert result.report.is_complete
        assert result.order is not None
        assert len(result.fills) == 1
        assert result.position is not None
        assert result.position.net_qty == Decimal("10")

    @pytest.mark.skipif(NAUTILUS_AVAILABLE, reason="Only relevant when Nautilus is absent")
    def test_default_router_uses_simulation(self) -> None:
        router = build_default_router(mode=ExecutionMode.SIMULATION)
        assert isinstance(router, SimulationRouter)


class TestWhenNautilusInstalled:
    @pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="Only relevant when Nautilus is installed")
    def test_live_router_initializes(self) -> None:
        router = NautilusRouter(mode=ExecutionMode.LIVE)
        assert router.mode == ExecutionMode.LIVE

    @pytest.mark.skipif(not NAUTILUS_AVAILABLE, reason="Only relevant when Nautilus is installed")
    def test_simulation_router_still_available(self) -> None:
        router = build_default_router(mode=ExecutionMode.SIMULATION)
        assert isinstance(router, SimulationRouter)
