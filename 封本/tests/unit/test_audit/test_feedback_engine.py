"""Tests for FeedbackEngine."""
import pytest
from datetime import datetime
from core.audit.feedback.engine import FeedbackEngine
from core.audit.schemas.decision_record import DecisionRecord, SignalSnapshot
from core.audit.schemas.execution_record import ExecutionRecord, FillSnapshot
from core.audit.schemas.risk_audit import RiskAudit, FilterCheckSnapshot
from core.audit.schemas.feedback import FeedbackType, FeedbackStatus


class TestFeedbackEngine:
    def test_scan_empty_returns_empty(self) -> None:
        engine = FeedbackEngine()
        feedbacks = engine.scan([], [], [])
        assert feedbacks == []

    def test_slippage_feedback_generated(self) -> None:
        engine = FeedbackEngine()
        records = []
        for i in range(25):
            records.append(
                ExecutionRecord(
                    audit_id=f"er-{i:03d}",
                    timestamp=datetime.utcnow(),
                    source_phase="Phase 3",
                    symbol="AAPL",
                    decision_id=f"d-{i:03d}",
                    plan_id=f"pp-{i:03d}",
                    order_type="MARKET",
                    estimated_slippage_bps=3.0,
                    realized_slippage_bps=10.0,  # bias = +7bps
                    fills=[],
                    total_requested_qty=100.0,
                    total_filled_qty=100.0,
                    fill_rate=1.0,
                    avg_execution_price=100.0,
                    arrival_price=100.0,
                )
            )
        feedbacks = engine.scan([], records, [])
        slip_feedbacks = [f for f in feedbacks if f.feedback_type == FeedbackType.SLIPPAGE_CALIBRATION]
        assert len(slip_feedbacks) >= 1
        fb = slip_feedbacks[0]
        assert fb.severity == "high"  # bias 7bps > 5bps threshold
        assert fb.metric_name == "slippage_bias_bps"
        assert fb.sample_size == 25

    def test_slippage_feedback_skipped_under_threshold(self) -> None:
        engine = FeedbackEngine()
        records = []
        for i in range(25):
            records.append(
                ExecutionRecord(
                    audit_id=f"er-{i:03d}",
                    timestamp=datetime.utcnow(),
                    source_phase="Phase 3",
                    symbol="TSLA",
                    decision_id=f"d-{i:03d}",
                    plan_id=f"pp-{i:03d}",
                    order_type="LIMIT",
                    estimated_slippage_bps=2.0,
                    realized_slippage_bps=3.0,  # bias = +1bps, < 2bps threshold
                    fills=[],
                    total_requested_qty=100.0,
                    total_filled_qty=100.0,
                    fill_rate=1.0,
                    avg_execution_price=100.0,
                    arrival_price=100.0,
                )
            )
        feedbacks = engine.scan([], records, [])
        slip_feedbacks = [f for f in feedbacks if f.feedback_type == FeedbackType.SLIPPAGE_CALIBRATION]
        assert len(slip_feedbacks) == 0

    def test_signal_decay_feedback_generated(self) -> None:
        engine = FeedbackEngine()
        records = []
        for i in range(15):
            records.append(
                DecisionRecord(
                    audit_id=f"dr-{i:03d}",
                    timestamp=datetime.utcnow(),
                    source_phase="Phase 6",
                    symbol="AAPL",
                    decision_id=f"d-{i:03d}",
                    bias="long_bias",
                    final_confidence=0.8,
                    target_direction="LONG",
                    target_quantity=500.0,
                    arbitration_confidence=0.8,
                    input_signals=[
                        SignalSnapshot(
                            source_module="technical",
                            signal_type="breakout",
                            direction="LONG",
                            confidence=0.7,
                        )
                    ],
                    realized_pnl_pct=-0.02,  # negative PnL in >72h bucket
                    signal_age_hours=80.0,   # >72h bucket
                )
            )
        feedbacks = engine.scan(records, [], [])
        decay_feedbacks = [f for f in feedbacks if f.feedback_type == FeedbackType.SIGNAL_DECAY]
        assert len(decay_feedbacks) >= 1

    def test_filter_pattern_feedback_high_veto_rate(self) -> None:
        engine = FeedbackEngine()
        audits = []
        for i in range(25):
            audits.append(
                RiskAudit(
                    audit_id=f"ra-{i:03d}",
                    timestamp=datetime.utcnow(),
                    source_phase="Phase 7",
                    symbol="AAPL",
                    decision_id=f"d-{i:03d}",
                    position_plan_id=f"pp-{i:03d}",
                    plan_bias="long_bias",
                    sizing_input_qty=500.0,
                    input_quantity=500.0,
                    final_quantity=0.0,
                    veto_triggered=True,
                    filter_results=[
                        FilterCheckSnapshot(
                            filter_name="loss_limit",
                            mode="veto",
                            passed=False,
                            raw_qty=500.0,
                            adjusted_qty=0.0,
                        )
                    ],
                    total_vetoes=1,
                    veto_filters=["loss_limit"],
                    regime="volatile",
                )
            )
        feedbacks = engine.scan([], [], audits)
        filter_feedbacks = [f for f in feedbacks if f.feedback_type == FeedbackType.FILTER_PATTERN]
        assert len(filter_feedbacks) >= 1
        fb = filter_feedbacks[0]
        assert fb.severity == "high"  # 100% veto rate > 30% threshold

    def test_feedback_status_pending(self) -> None:
        engine = FeedbackEngine()
        records = []
        for i in range(20):  # MIN_SAMPLES=20 required
            records.append(
                ExecutionRecord(
                    audit_id=f"er-{i:03d}",
                    timestamp=datetime.utcnow(),
                    source_phase="Phase 3",
                    symbol="AAPL",
                    decision_id=f"d-{i:03d}",
                    plan_id=f"pp-{i:03d}",
                    order_type="MARKET",
                    estimated_slippage_bps=2.0,
                    realized_slippage_bps=10.0,  # bias=+8bps, >5bps → high severity
                    fills=[],
                    total_requested_qty=100.0,
                    total_filled_qty=100.0,
                    fill_rate=1.0,
                    avg_execution_price=100.0,
                    arrival_price=100.0,
                )
            )
        feedbacks = engine.scan([], records, [])
        assert len(feedbacks) >= 1
        for fb in feedbacks:
            assert fb.status == FeedbackStatus.PENDING
            assert fb.feedback_id.startswith("fb-")

    def test_factor_attribution_feedback_low_ir(self) -> None:
        engine = FeedbackEngine()
        records = []
        for i in range(35):
            records.append(
                DecisionRecord(
                    audit_id=f"dr-{i:03d}",
                    timestamp=datetime.utcnow(),
                    source_phase="Phase 6",
                    symbol="AAPL",
                    decision_id=f"d-{i:03d}",
                    bias="long_bias",
                    final_confidence=0.8,
                    target_direction="LONG",
                    target_quantity=500.0,
                    arbitration_confidence=0.8,
                    input_signals=[
                        SignalSnapshot(
                            source_module="macro",
                            signal_type="rate_forecast",
                            direction="SHORT",
                            confidence=0.5,
                        )
                    ],
                    realized_pnl_pct=0.001,  # tiny positive, low IR
                )
            )
        feedbacks = engine.scan(records, [], [])
        factor_feedbacks = [f for f in feedbacks if f.feedback_type == FeedbackType.FACTOR_ATTRIBUTION]
        assert len(factor_feedbacks) >= 1
