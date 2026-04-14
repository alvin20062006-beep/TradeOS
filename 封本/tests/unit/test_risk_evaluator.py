"""
Tests: Execution Quality Evaluator
================================
Pre-trade estimate + Post-trade evaluation
"""

from __future__ import annotations

from datetime import datetime

from core.risk.evaluator import _score_to_rating, estimate, evaluate
from core.risk.schemas import ExecutionPlan
from core.schemas import Direction, ExecutionQuality, FillRecord, OrderRecord, OrderType, Side


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="test-plan",
        position_plan_id="test-pp",
        decision_id="test-decision",
        timestamp=datetime.utcnow(),
        symbol="AAPL",
        direction=Direction.LONG,
        target_quantity=1000.0,
        notional_value=100_000.0,
        algorithm=OrderType.VWAP,
        estimated_impact_bps=30.0,
        estimated_slippage_bps=10.0,
    )


class TestPreTradeEstimate:
    def test_estimate_returns_report(self) -> None:
        ep = _plan()
        report = estimate(
            plan=ep,
            avg_daily_volume_20d=1_000_000.0,
            realized_vol_20d=0.20,
        )
        assert report.is_pre_trade is True
        assert report.plan_id == ep.plan_id
        assert report.estimated_impact_bps is not None
        assert report.estimated_participation_rate is not None
        assert report.participation_risk in ("low", "medium", "high")


class TestPostTradeEvaluation:
    def test_evaluate_with_fills(self) -> None:
        ep = ExecutionPlan(
            plan_id="test-plan",
            position_plan_id="test-pp",
            decision_id="test-decision",
            timestamp=datetime.utcnow(),
            symbol="AAPL",
            direction=Direction.LONG,
            target_quantity=100.0,
            notional_value=10_000.0,
            algorithm=OrderType.VWAP,
            estimated_impact_bps=30.0,
            estimated_slippage_bps=10.0,
        )
        fills = [
            FillRecord(
                fill_id="f1",
                order_id="o1",
                timestamp=datetime.utcnow(),
                price=100.10,
                quantity=50.0,
                side=Side.BUY,
            ),
            FillRecord(
                fill_id="f2",
                order_id="o1",
                timestamp=datetime.utcnow(),
                price=100.12,
                quantity=50.0,
                side=Side.BUY,
            ),
        ]
        report = evaluate(
            plan=ep,
            fills=fills,
            orders=[],
            arrival_price=100.00,
        )
        assert report.is_pre_trade is False
        assert report.realized_slippage_bps is not None
        assert report.execution_score >= 0
        assert report.quality_rating in list(ExecutionQuality)

    def test_no_fills_returns_failed(self) -> None:
        ep = _plan()
        report = evaluate(plan=ep, fills=[], orders=[])
        assert report.quality_rating == ExecutionQuality.FAILED


class TestScoreToRating:
    def test_ratings(self) -> None:
        assert _score_to_rating(0.90) == ExecutionQuality.EXCELLENT
        assert _score_to_rating(0.75) == ExecutionQuality.GOOD
        assert _score_to_rating(0.55) == ExecutionQuality.FAIR
        assert _score_to_rating(0.35) == ExecutionQuality.POOR
        assert _score_to_rating(0.10) == ExecutionQuality.FAILED
