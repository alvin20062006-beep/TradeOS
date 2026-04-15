"""Tests for ExecutionAuditor."""
import pytest
from datetime import datetime, timedelta
from core.audit.engine.execution_audit import ExecutionAuditor
from core.audit.schemas.execution_record import FillSnapshot
from core.schemas import ExecutionQuality


class TestExecutionAuditor:
    def test_ingest_single_fill(self) -> None:
        auditor = ExecutionAuditor()
        fills = [
            {
                "slice_id": "s1",
                "filled_qty": 100.0,
                "fill_price": 150.5,
                "fill_time": datetime.utcnow(),
                "slippage_bps": 2.0,
                "is_leaving_qty": False,
                "quantity": 100.0,
            }
        ]
        record = auditor.ingest(
            fills=fills,
            plan_id="pp-001",
            symbol="AAPL",
            decision_id="d-001",
            order_type="MARKET",
            algorithm="vwap_default",
            position_plan_id="pp-001",
        )

        assert record.audit_id.startswith("er-")
        assert record.symbol == "AAPL"
        assert record.plan_id == "pp-001"
        assert record.order_type == "MARKET"
        assert record.algorithm == "vwap_default"
        assert record.total_filled_qty == 100.0
        assert len(record.fills) == 1
        assert record.fills[0].slice_id == "s1"
        assert record.fills[0].filled_qty == 100.0
        assert record.fills[0].fill_price == 150.5

    def test_ingest_multiple_fills_weighted_avg_price(self) -> None:
        auditor = ExecutionAuditor()
        fills = [
            {"slice_id": "s1", "filled_qty": 60.0, "fill_price": 100.0,
             "fill_time": datetime.utcnow(), "slippage_bps": 0.0, "is_leaving_qty": False, "quantity": 100.0},
            {"slice_id": "s2", "filled_qty": 40.0, "fill_price": 101.0,
             "fill_time": datetime.utcnow(), "slippage_bps": 0.0, "is_leaving_qty": False, "quantity": 100.0},
        ]
        record = auditor.ingest(
            fills=fills,
            plan_id="pp-002",
            symbol="TSLA",
            decision_id="d-002",
            order_type="VWAP",
        )
        # avg_price = (60*100 + 40*101) / 100 = 100.4
        assert abs(record.avg_execution_price - 100.4) < 0.01

    def test_realized_slippage_calculation(self) -> None:
        auditor = ExecutionAuditor()
        fills = [
            {"slice_id": "s1", "filled_qty": 100.0, "fill_price": 150.0,
             "fill_time": datetime.utcnow(), "slippage_bps": 5.0, "is_leaving_qty": False, "quantity": 100.0},
        ]
        record = auditor.ingest(
            fills=fills,
            plan_id="pp-003",
            symbol="AAPL",
            decision_id="d-003",
            order_type="MARKET",
            evaluator_pre_result={"arrival_price": 150.0},
        )
        # realized_slippage = (150 - 150) / 150 * 10000 = 0
        assert abs(record.realized_slippage_bps) < 0.01

    def test_pre_post_evaluator_results(self) -> None:
        auditor = ExecutionAuditor()
        fills = [{"slice_id": "s1", "filled_qty": 200.0, "fill_price": 99.0,
                  "fill_time": datetime.utcnow(), "slippage_bps": -2.0, "is_leaving_qty": False, "quantity": 200.0}]
        record = auditor.ingest(
            fills=fills,
            plan_id="pp-004",
            symbol="NVDA",
            decision_id="d-004",
            order_type="LIMIT",
            evaluator_pre_result={
                "arrival_price": 100.0,
                "estimated_slippage_bps": 3.0,
                "estimated_impact_bps": 1.5,
                "estimated_fill_rate": 0.98,
            },
            evaluator_post_result={
                "execution_quality_score": 0.88,
                "quality_rating": "good",
                "realized_impact_bps": 1.2,
            },
        )
        assert record.estimated_slippage_bps == 3.0
        assert record.estimated_impact_bps == 1.5
        assert record.execution_quality_score == 0.88
        assert record.quality_rating == ExecutionQuality.GOOD

    def test_execution_duration(self) -> None:
        auditor = ExecutionAuditor()
        start = datetime.utcnow()
        end = start + timedelta(seconds=30)
        fills = [{"slice_id": "s1", "filled_qty": 50.0, "fill_price": 200.0,
                  "fill_time": end, "slippage_bps": 0.0, "is_leaving_qty": False, "quantity": 50.0}]
        record = auditor.ingest(
            fills=fills,
            plan_id="pp-005",
            symbol="SPY",
            decision_id="d-005",
            order_type="ADAPTIVE",
            execution_start=start,
            execution_end=end,
        )
        assert record.execution_duration_seconds == 30.0

    def test_fill_snapshot_from_fill(self) -> None:
        snap = FillSnapshot.from_fill({
            "slice_id": "x1",
            "filled_qty": 75.0,
            "fill_price": 88.5,
            "fill_time": datetime.utcnow(),
            "slippage_bps": 1.5,
            "is_leaving_qty": True,
        })
        assert snap.slice_id == "x1"
        assert snap.filled_qty == 75.0
        assert snap.slippage_bps == 1.5
        assert snap.is_leaving_qty is True
