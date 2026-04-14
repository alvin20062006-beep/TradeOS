"""Tests for RiskAuditor."""
import pytest
from datetime import datetime
from core.audit.engine.risk_audit import RiskAuditor
from core.audit.schemas.risk_audit import FilterCheckSnapshot


class FakePositionPlan:
    """Fake Phase 7 PositionPlan for testing."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestRiskAuditor:
    def test_ingest_veto_triggered(self) -> None:
        auditor = RiskAuditor()
        plan = FakePositionPlan(
            plan_id="pp-001",
            decision_id="d-001",
            symbol="AAPL",
            bias="long_bias",
            base_quantity=500.0,
            final_quantity=0.0,
            veto_triggered=True,
            limit_checks=[
                {
                    "limit_name": "loss_limit",
                    "passed": False,
                    "mode": "veto",
                    "actual_value": -500.0,
                    "limit_value": -200.0,
                    "details": "daily loss exceeds limit",
                }
            ],
        )
        audit = auditor.ingest(plan)

        assert audit.audit_id.startswith("ra-")
        assert audit.symbol == "AAPL"
        assert audit.position_plan_id == "pp-001"
        assert audit.veto_triggered is True
        assert audit.final_quantity == 0.0
        assert audit.total_vetoes == 1
        assert audit.veto_filters == ["loss_limit"]
        assert len(audit.filter_results) == 1

    def test_ingest_cap_adjustment(self) -> None:
        auditor = RiskAuditor()
        plan = FakePositionPlan(
            plan_id="pp-002",
            decision_id="d-002",
            symbol="TSLA",
            bias="long_bias",
            base_quantity=800.0,
            final_quantity=200.0,
            veto_triggered=False,
            limit_checks=[
                {
                    "limit_name": "liquidity_cap",
                    "passed": True,
                    "mode": "cap",
                    "actual_value": 200.0,
                    "details": "qty capped by ADV limit",
                }
            ],
        )
        audit = auditor.ingest(plan)

        assert audit.veto_triggered is False
        assert audit.total_adjustments == 1
        assert audit.total_vetoes == 0
        assert audit.final_quantity == 200.0
        assert audit.filter_results[0].mode == "cap"

    def test_ingest_multi_filter_chain(self) -> None:
        auditor = RiskAuditor()
        plan = FakePositionPlan(
            plan_id="pp-003",
            decision_id="d-003",
            symbol="NVDA",
            bias="long_bias",
            base_quantity=1000.0,
            final_quantity=0.0,
            veto_triggered=True,
            limit_checks=[
                {
                    "limit_name": "loss_limit",
                    "passed": False,
                    "mode": "veto",
                    "actual_value": -800.0,
                    "details": "loss exceeds",
                },
                {
                    "limit_name": "drawdown_limit",
                    "passed": False,
                    "mode": "veto",
                    "actual_value": -0.08,
                    "details": "drawdown exceeds",
                },
                {
                    "limit_name": "position_limit",
                    "passed": True,
                    "mode": "pass",
                    "actual_value": 500.0,
                    "details": "within limit",
                },
            ],
        )
        audit = auditor.ingest(plan)

        assert audit.total_vetoes == 2
        assert audit.total_adjustments == 0
        assert audit.veto_filters == ["loss_limit", "drawdown_limit"]
        assert len(audit.filter_results) == 3
        passed_frs = [fr for fr in audit.filter_results if fr.passed]
        assert len(passed_frs) == 1

    def test_ingest_regime_metadata(self) -> None:
        auditor = RiskAuditor()
        plan = FakePositionPlan(
            plan_id="pp-004",
            decision_id="d-004",
            symbol="SPY",
            bias="exit_bias",
            base_quantity=200.0,
            final_quantity=200.0,
            veto_triggered=False,
            limit_checks=[],
        )
        audit = auditor.ingest(
            plan,
            regime="trending",
            volatility_regime="high",
        )

        assert audit.regime == "trending"
        assert audit.volatility_regime == "high"

    def test_filter_check_snapshot_from_dict(self) -> None:
        lc = {
            "limit_name": "slippage_limit",
            "mode": "veto",
            "passed": False,
            "raw_qty": 300.0,
            "adjusted_qty": 0.0,
            "limit_value": 10.0,
            "actual_value": 15.0,
            "details": "slippage exceeds limit",
        }
        snap = FilterCheckSnapshot.from_limit_check(lc)
        assert snap.filter_name == "slippage_limit"
        assert snap.mode == "veto"
        assert snap.passed is False
        assert snap.raw_qty == 300.0
        assert snap.adjusted_qty == 0.0
        assert snap.limit_value == 10.0
        assert snap.actual_value == 15.0

    def test_ingest_empty_limit_checks(self) -> None:
        auditor = RiskAuditor()
        plan = FakePositionPlan(
            plan_id="pp-005",
            decision_id="d-005",
            symbol="QQQ",
            bias="long_bias",
            base_quantity=500.0,
            final_quantity=500.0,
            veto_triggered=False,
            limit_checks=[],
        )
        audit = auditor.ingest(plan)

        assert audit.filter_results == []
        assert audit.total_vetoes == 0
        assert audit.total_adjustments == 0
        assert audit.veto_triggered is False

    def test_veto_filters_list_correct(self) -> None:
        auditor = RiskAuditor()
        plan = FakePositionPlan(
            plan_id="pp-006",
            decision_id="d-006",
            symbol="AAPL",
            bias="long_bias",
            base_quantity=500.0,
            final_quantity=0.0,
            veto_triggered=True,
            limit_checks=[
                {"limit_name": "correlation_limit", "passed": True, "mode": "pass",
                 "actual_value": 0.2, "details": ""},
                {"limit_name": "loss_limit", "passed": False, "mode": "veto",
                 "actual_value": -500.0, "details": ""},
            ],
        )
        audit = auditor.ingest(plan)
        assert "loss_limit" in audit.veto_filters
        assert "correlation_limit" not in audit.veto_filters
