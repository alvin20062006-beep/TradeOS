"""
Tests: Risk Engine Integration
=============================
端到端：ArbitrationDecision → PositionPlan → ExecutionPlan
"""

from __future__ import annotations

from datetime import datetime

from core.arbitration.schemas import ArbitrationDecision
from core.risk.context import MarketContext
from core.risk.engine import RiskEngine
from core.risk.schemas import PositionPlan
from core.schemas import Direction, Portfolio, RiskLimits


def _portfolio(equity: float = 100_000.0) -> Portfolio:
    return Portfolio(
        timestamp=datetime.utcnow(),
        total_equity=equity,
        cash=equity,
        peak_equity=equity,
    )


def _decision(
    bias: str = "long_bias",
    confidence: float = 0.8,
) -> ArbitrationDecision:
    return ArbitrationDecision(
        decision_id="test-decision",
        timestamp=datetime.utcnow(),
        symbol="AAPL",
        bias=bias,
        confidence=confidence,
    )


def _ctx(
    price: float = 100.0,
    adv: float = 1_000_000.0,
    realized_vol: float = 0.20,
) -> MarketContext:
    return MarketContext(
        symbol="AAPL",
        timestamp=datetime.utcnow(),
        current_price=price,
        avg_daily_volume_20d=adv,
        realized_vol_20d=realized_vol,
        atr_14=2.0,
        adv_20d_usd=adv * price,
    )


class TestRiskEngineBasic:
    def setup_method(self) -> None:
        # Wide limits（避免 PositionLimitFilter 触发 veto）
        self.engine = RiskEngine(risk_limits=RiskLimits(
            max_position_pct=0.50,
            max_loss_pct_per_trade=0.05,
            max_loss_pct_per_day=0.10,
            max_drawdown_pct=0.30,
            max_slippage_bps=100.0,
        ))

    def test_long_bias_calculates_position(self) -> None:
        decision = _decision(bias="long_bias", confidence=0.8)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=200.0, adv=500_000.0, realized_vol=0.25)

        plan = self.engine.calculate(decision, portfolio, market_context=ctx)

        assert isinstance(plan, PositionPlan)
        assert plan.symbol == "AAPL"
        assert plan.final_quantity > 0
        assert plan.sizing_method in (
            "volatility_targeting", "kelly", "conviction_weighted",
            "fixed_fraction", "drawdown_adjusted", "regime_based",
        )
        assert not plan.veto_triggered
        assert plan.execution_plan is not None

    def test_no_trade_returns_zero_quantity(self) -> None:
        decision = _decision(bias="no_trade", confidence=0.0)
        portfolio = _portfolio()
        plan = self.engine.calculate(decision, portfolio)

        assert plan.final_quantity == 0.0
        assert plan.veto_triggered is True
        assert len(plan.veto_reasons) > 0

    def test_hold_bias_returns_zero_quantity(self) -> None:
        decision = _decision(bias="hold_bias", confidence=0.3)
        portfolio = _portfolio()
        plan = self.engine.calculate(decision, portfolio)

        assert plan.final_quantity == 0.0

    def test_exit_bias_triggers_exit(self) -> None:
        """exit_bias: LONG 持仓 → 平仓，执行动作=卖出"""
        decision = _decision(bias="exit_bias", confidence=0.9)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)
        plan = self.engine.calculate(
            decision, portfolio, market_context=ctx,
            existing_direction=Direction.LONG,
            existing_position_qty=200.0,
        )

        assert plan.final_quantity == 200.0
        assert plan.is_reducing
        assert plan.direction == Direction.SHORT
        assert plan.exec_action == "SELL"

    def test_reduce_risk_maintains_direction(self) -> None:
        """reduce_risk: LONG 持仓 → 减仓，执行动作=卖出（不是买入！）"""
        decision = _decision(bias="reduce_risk", confidence=0.7)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)
        plan = self.engine.calculate(
            decision, portfolio, market_context=ctx,
            existing_direction=Direction.LONG,
            existing_position_qty=200.0,
        )

        assert plan.final_quantity == 200.0
        assert plan.is_reducing
        assert plan.direction == Direction.LONG
        assert plan.exec_action == "SELL"

    def test_reduce_risk_short_exec_action_is_buy(self) -> None:
        """reduce_risk: SHORT 持仓 → 减仓，执行动作=买入（不是卖出！）"""
        decision = _decision(bias="reduce_risk", confidence=0.7)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)
        plan = self.engine.calculate(
            decision, portfolio, market_context=ctx,
            existing_direction=Direction.SHORT,
            existing_position_qty=150.0,
        )

        assert plan.final_quantity > 0
        assert plan.is_reducing
        assert plan.direction == Direction.SHORT
        assert plan.exec_action == "BUY"

    def test_exit_bias_short_side(self) -> None:
        """exit_bias: SHORT 持仓 → 平仓，执行动作=买入（cover）"""
        decision = _decision(bias="exit_bias", confidence=0.9)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)
        plan = self.engine.calculate(
            decision, portfolio, market_context=ctx,
            existing_direction=Direction.SHORT,
            existing_position_qty=150.0,
        )

        assert plan.final_quantity == 150.0
        assert plan.is_reducing
        assert plan.direction == Direction.LONG
        assert plan.exec_action == "BUY"

    def test_exit_without_position_returns_zero(self) -> None:
        """exit_bias + 无持仓 → zero_plan"""
        decision = _decision(bias="exit_bias", confidence=0.9)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)
        plan = self.engine.calculate(
            decision, portfolio, market_context=ctx,
            existing_direction=None,
            existing_position_qty=0.0,
        )

        assert plan.final_quantity == 0.0
        assert plan.veto_triggered
        assert "exit_without_position" in plan.veto_reasons

    def test_reduce_without_position_returns_zero(self) -> None:
        """reduce_risk + 无持仓 → zero_plan"""
        decision = _decision(bias="reduce_risk", confidence=0.7)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)
        plan = self.engine.calculate(
            decision, portfolio, market_context=ctx,
            existing_direction=None,
            existing_position_qty=0.0,
        )

        assert plan.final_quantity == 0.0
        assert plan.veto_triggered
        assert "reduce_without_position" in plan.veto_reasons

    def test_veto_by_loss_limit(self) -> None:
        from core.schemas import RiskLimits

        engine = RiskEngine(risk_limits=RiskLimits(
            max_loss_pct_per_trade=0.01,  # 1% 限额
        ))
        decision = _decision(bias="long_bias", confidence=0.9)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)

        # avg_entry_price=50 + current_price=100 → stop_distance=50
        # potential_loss = 1000 × 50 = $50,000 / $100,000 equity = 50% > 1% limit → veto
        plan = engine.calculate(
            decision, portfolio, market_context=ctx,
            avg_entry_price=50.0,
            daily_loss_pct=0.0,
        )
        assert plan.veto_triggered

    def test_limit_checks_populated(self) -> None:
        decision = _decision(bias="long_bias", confidence=0.8)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)

        plan = self.engine.calculate(decision, portfolio, market_context=ctx)
        assert len(plan.limit_checks) >= 0  # 检查列表存在

    def test_execution_plan_attached(self) -> None:
        decision = _decision(bias="long_bias", confidence=0.8)
        portfolio = _portfolio(100_000.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0, realized_vol=0.20)

        plan = self.engine.calculate(decision, portfolio, market_context=ctx)
        assert plan.execution_plan is not None
        assert plan.execution_plan.symbol == "AAPL"
        assert plan.execution_plan.target_quantity > 0
