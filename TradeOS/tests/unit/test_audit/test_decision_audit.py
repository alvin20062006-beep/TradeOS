"""Tests for DecisionAuditor."""
import pytest
from datetime import datetime
from core.audit.engine.decision_audit import DecisionAuditor
from core.audit.schemas.decision_record import SignalSnapshot


class FakeDecision:
    """Fake ArbitrationDecision for testing."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestDecisionAuditor:
    def test_ingest_minimal(self) -> None:
        auditor = DecisionAuditor()
        decision = FakeDecision(
            decision_id="d-001",
            symbol="AAPL",
            bias="long_bias",
            confidence=0.8,
            target_direction="LONG",
            target_quantity=500.0,
            source_signals=[],
        )
        record = auditor.ingest(decision)
        assert record.audit_id.startswith("dr-")
        assert record.symbol == "AAPL"
        assert record.bias == "long_bias"
        assert record.final_confidence == 0.8
        assert record.input_signals == []
        assert record.target_direction == "LONG"

    def test_ingest_with_signals(self) -> None:
        auditor = DecisionAuditor()
        signals = [
            {
                "source_module": "technical",
                "signal_type": "breakout",
                "direction": "LONG",
                "confidence": 0.7,
                "regime": "trending",
                "score": 0.85,
                "metadata": {"period": "daily"},
            }
        ]
        decision = FakeDecision(
            decision_id="d-002",
            symbol="TSLA",
            bias="exit_bias",
            confidence=0.6,
            target_direction="SHORT",
            target_quantity=300.0,
            source_signals=signals,
        )
        record = auditor.ingest(decision, realized_pnl_pct=0.025)
        assert len(record.input_signals) == 1
        sig = record.input_signals[0]
        assert sig.source_module == "technical"
        assert sig.signal_type == "breakout"
        assert sig.direction == "LONG"
        assert sig.confidence == 0.7
        assert sig.regime == "trending"
        assert sig.metadata == {"period": "daily"}
        assert record.realized_pnl_pct == 0.025

    def test_signal_snapshot_roundtrip(self) -> None:
        snap = SignalSnapshot(
            source_module="chan",
            signal_type="divergence",
            direction="SHORT",
            confidence=0.65,
            regime="volatile",
            score=0.55,
            metadata={"缠论级别": "30f"},
        )
        assert snap.source_module == "chan"
        assert snap.metadata == {"缠论级别": "30f"}
        json_str = snap.model_dump_json()
        restored = SignalSnapshot.model_validate_json(json_str)
        assert restored.source_module == snap.source_module
        assert restored.metadata == snap.metadata

    def test_no_signals_returns_empty_list(self) -> None:
        auditor = DecisionAuditor()
        decision = FakeDecision(
            decision_id="d-003",
            symbol="NVDA",
            bias="hold",
            confidence=0.0,
            target_direction="FLAT",
            target_quantity=0.0,
            source_signals=None,
        )
        record = auditor.ingest(decision)
        assert record.input_signals == []

    def test_post_fields_passed_through(self) -> None:
        auditor = DecisionAuditor()
        decision = FakeDecision(
            decision_id="d-004",
            symbol="SPY",
            bias="long_bias",
            confidence=0.9,
            target_direction="LONG",
            target_quantity=1000.0,
            source_signals=[],
        )
        record = auditor.ingest(
            decision,
            realized_pnl_pct=-0.015,
            signal_age_hours=6.5,
            holding_period_hours=48.0,
            entry_price=450.0,
            exit_price=442.5,
        )
        assert record.realized_pnl_pct == -0.015
        assert record.signal_age_hours == 6.5
        assert record.holding_period_hours == 48.0
        assert record.entry_price == 450.0
        assert record.exit_price == 442.5
