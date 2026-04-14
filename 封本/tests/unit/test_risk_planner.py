"""
Tests: Execution Planner
=====================
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.risk.context import MarketContext
from core.risk.planner import _select_algorithm, plan
from core.risk.schemas import PositionPlan
from core.schemas import ArbitrationDecision, Direction, OrderType, Portfolio, RiskLimits


def _portfolio(equity: float = 100_000.0) -> Portfolio:
    return Portfolio(
        timestamp=None,
        total_equity=equity,
        cash=equity,
    )


def _decision(bias: str = "long_bias", confidence: float = 0.8) -> ArbitrationDecision:
    return ArbitrationDecision(
        decision_id="test-decision",
        timestamp=None,
        symbol="AAPL",
        direction=Direction.LONG,
        confidence=confidence,
        regime=None,
        bias=bias,
        execution_style=OrderType.MARKET,
    )


def _ctx(
    price: float = 100.0,
    adv: float = 1_000_000.0,
    realized_vol: float = 0.20,
) -> MarketContext:
    return MarketContext(
        symbol="AAPL",
        timestamp=None,
        current_price=price,
        avg_daily_volume_20d=adv,
        realized_vol_20d=realized_vol,
        adv_20d_usd=adv * price,
    )


class TestAlgorithmSelection:
    def test_exit_bias_selects_market(self) -> None:
        pp = _position_plan(bias="exit_bias")
        alg, _ = _select_algorithm(pp, 500, None, "medium")
        assert alg == OrderType.MARKET

    def test_reduce_bias_selects_market(self) -> None:
        pp = _position_plan(bias="reduce_risk")
        alg, _ = _select_algorithm(pp, 500, None, "medium")
        assert alg == OrderType.MARKET

    def test_high_impact_selects_iceberg(self) -> None:
        pp = _position_plan(bias="long_bias")
        alg, _ = _select_algorithm(pp, 150, None, "medium")
        assert alg == OrderType.ICEBERG

    def test_medium_impact_selects_vwap(self) -> None:
        pp = _position_plan(bias="long_bias")
        alg, _ = _select_algorithm(pp, 70, None, "medium")
        assert alg == OrderType.VWAP

    def test_high_volatility_selects_adaptive(self) -> None:
        pp = _position_plan(bias="long_bias")
        ctx = _ctx(realized_vol=0.40)
        alg, _ = _select_algorithm(pp, 30, ctx, "medium")
        assert alg == OrderType.ADAPTIVE

    def test_low_impact_medium_urgency_selects_limit(self) -> None:
        pp = _position_plan(bias="long_bias")
        alg, _ = _select_algorithm(pp, 30, None, "medium")
        assert alg == OrderType.LIMIT

    def test_low_impact_high_urgency_selects_market(self) -> None:
        pp = _position_plan(bias="long_bias")
        alg, _ = _select_algorithm(pp, 30, None, "high")
        assert alg == OrderType.MARKET


def _position_plan(
    bias: str = "long_bias",
    qty: float = 100.0,
    symbol: str = "AAPL",
) -> PositionPlan:
    return PositionPlan(
        plan_id="test-pp",
        decision_id="test-decision",
        timestamp=datetime.utcnow(),
        symbol=symbol,
        bias=bias,
        arbitration_confidence=0.8,
        direction=Direction.LONG,
        sizing_method="volatility_targeting",
        base_quantity=qty,
        final_quantity=qty,
        notional_value=qty * 100.0,
        current_price=100.0,
    )


class TestExecutionPlanGeneration:
    def test_plan_with_valid_position(self) -> None:
        pp = _position_plan(qty=100.0)
        ctx = _ctx(price=100.0, adv=1_000_000.0)
        ep = plan(pp, market_context=ctx, urgency="medium")
        assert ep.plan_id is not None
        assert ep.symbol == "AAPL"
        assert ep.target_quantity == 100.0
        assert ep.algorithm in [OrderType.LIMIT, OrderType.VWAP, OrderType.MARKET]
        assert ep.estimated_impact_bps >= 0

    def test_plan_zero_quantity(self) -> None:
        pp = _position_plan(qty=0.0, bias="no_trade")
        ep = plan(pp, market_context=None, urgency="medium")
        assert ep.target_quantity == 0.0
