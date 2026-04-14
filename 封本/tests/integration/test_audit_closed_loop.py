"""Integration test: full Phase 8 audit → feedback → Phase 4 closed loop."""
import pytest
import tempfile
from datetime import datetime
from core.audit.engine.decision_audit import DecisionAuditor
from core.audit.engine.execution_audit import ExecutionAuditor
from core.audit.engine.risk_audit import RiskAuditor
from core.audit.feedback.engine import FeedbackEngine
from core.audit.closed_loop.feedback_registry import FeedbackRegistry
from core.audit.closed_loop.phase4_updater import Phase4Updater
from core.audit.schemas.decision_record import DecisionRecord, SignalSnapshot
from core.audit.schemas.execution_record import ExecutionRecord, FillSnapshot
from core.audit.schemas.risk_audit import RiskAudit, FilterCheckSnapshot
from core.audit.schemas.feedback import FeedbackType, FeedbackStatus


class FakeArbitrationDecision:
    """Fake Phase 6 ArbitrationDecision."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestAuditClosedLoopIntegration:
    """
    完整闭环测试：

    1. DecisionAuditor → DecisionRecord[]
    2. ExecutionAuditor → ExecutionRecord[]
    3. RiskAuditor → RiskAudit[]
    4. FeedbackEngine.scan() → Feedback[]
    5. FeedbackRegistry.append() → persisted
    6. Phase4Updater.process() → Phase4CandidateUpdate[]
    7. 验证 candidate_update 结构正确
    """

    def test_full_closed_loop_one_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = FeedbackRegistry(base_path=tmpdir + "/feedback")
            updater = Phase4Updater(staging_path=tmpdir + "/candidates")

            # ── Step 1: Decision Records ────────────────────────
            dec_auditor = DecisionAuditor()
            decision_records = []
            for i in range(15):
                decision_records.append(
                    dec_auditor.ingest(
                        FakeArbitrationDecision(
                            decision_id=f"d-{i:03d}",
                            symbol="AAPL",
                            bias="long_bias",
                            confidence=0.75,
                            target_direction="LONG",
                            target_quantity=500.0,
                            source_signals=[
                                {
                                    "source_module": "technical",
                                    "signal_type": "breakout",
                                    "direction": "LONG",
                                    "confidence": 0.7,
                                    "regime": "trending",
                                    "score": 0.8,
                                }
                            ],
                        ),
                        realized_pnl_pct=0.02,
                        signal_age_hours=8.0,
                    )
                )

            # ── Step 2: Execution Records ──────────────────────
            exec_auditor = ExecutionAuditor()
            exec_records = []
            for i in range(25):
                exec_records.append(
                    exec_auditor.ingest(
                        fills=[
                            {
                                "slice_id": f"s-{i}",
                                "filled_qty": 100.0,
                                "fill_price": 150.0,
                                "fill_time": datetime.utcnow(),
                                "slippage_bps": 0.0,
                                "is_leaving_qty": False,
                                "quantity": 100.0,
                            }
                        ],
                        plan_id=f"pp-{i:03d}",
                        symbol="AAPL",
                        decision_id=f"d-{i:03d}",
                        order_type="MARKET",
                        evaluator_pre_result={"arrival_price": 150.0},
                        position_plan_id=f"pp-{i:03d}",
                    )
                )

            # ── Step 3: Risk Audits ────────────────────────────
            risk_auditor = RiskAuditor()
            risk_audits = []
            for i in range(25):
                plan = FakeArbitrationDecision(
                    decision_id=f"d-{i:03d}",
                    symbol="AAPL",
                    bias="long_bias",
                    source_signals=[],
                    plan_id=f"pp-{i:03d}",
                    plan_bias="long_bias",
                    base_quantity=500.0,
                    final_quantity=500.0,
                    veto_triggered=False,
                    limit_checks=[],
                )
                risk_audits.append(risk_auditor.ingest(plan))

            # Override with actual position plan
            for ra in risk_audits:
                # Simulate filter chain: loss_limit triggers veto in volatile regime
                ra.filter_results = [
                    FilterCheckSnapshot(
                        filter_name="loss_limit",
                        mode="veto",
                        passed=False,
                        raw_qty=500.0,
                        adjusted_qty=0.0,
                    )
                ]
                ra.veto_triggered = True
                ra.total_vetoes = 1
                ra.veto_filters = ["loss_limit"]
                ra.regime = "volatile"

            # ── Step 4: FeedbackEngine.scan() ──────────────────
            fb_engine = FeedbackEngine()
            feedbacks = fb_engine.scan(
                decision_records=decision_records,
                execution_records=exec_records,
                risk_audits=risk_audits,
            )

            # Verify feedback types present
            # Note: SIGNAL_DECAY requires negative PnL in >=24h bucket.
            # SLIPPAGE_CALIBRATION requires realized!=estimated.
            # This test only guarantees FILTER_PATTERN due to 100% veto_rate.
            fb_types = {fb.feedback_type for fb in feedbacks}
            assert FeedbackType.FILTER_PATTERN in fb_types  # 100% veto_rate in volatile regime
            assert len(feedbacks) >= 1  # at least one feedback generated

            # ── Step 5: FeedbackRegistry.append() ───────────────
            reg.append_many(feedbacks)
            stored = reg.read_all()
            assert len(stored) >= 1  # at least FILTER_PATTERN

            pending = reg.read_unprocessed()
            assert len(pending) >= 1

            # ── Step 6: Phase4Updater.process() ─────────────────
            candidates = updater.process(reg)

            assert len(candidates) >= 1  # at least one candidate update
            for cu in candidates:
                # candidate structure must be valid
                assert hasattr(cu, "suggestion")
                assert hasattr(cu, "flag")
                assert hasattr(cu, "candidate_update")
                assert cu.suggestion != ""
                assert cu.flag is not None
                assert cu.candidate_update is not None
                # phase4_suggestion not directly written to Phase 4 registry
                assert cu.candidate_update.get("registry") in [
                    "ExperimentRegistry",
                    "LabelSetRegistry",
                    "ModelRegistry",
                    "AlphaFactorRegistry",
                ]

    def test_mark_reviewed_then_process(self) -> None:
        """After mark_reviewed, Phase4Updater should not reprocess same feedback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = FeedbackRegistry(base_path=tmpdir)
            updater = Phase4Updater(staging_path=tmpdir + "/candidates")

            # Create and append one feedback
            from core.audit.schemas.feedback import Feedback
            fb = Feedback(
                feedback_id="fb-int-001",
                feedback_type=FeedbackType.FILTER_PATTERN,
                severity="high",
                symbol=None,
                sample_size=30,
                evidence={"veto_rate": 0.45},
                metric_name="filter_veto_rate",
                metric_value=0.45,
                threshold_breach=True,
                suggested_action="retrain model",
                confidence=0.8,
                source_audit_ids=["ra-001", "ra-002"],
            )
            reg.append(fb)

            # First run: gets processed
            c1 = updater.process(reg)
            assert len(c1) == 1

            # Mark as reviewed
            reg.mark_reviewed("fb-int-001", "alvin")

            # Second run: should not reprocess reviewed feedback
            c2 = updater.process(reg)
            reviewed_ids = [cu.feedback_id for cu in c2]
            assert "fb-int-001" not in reviewed_ids

    def test_separation_of_review_and_feedback(self) -> None:
        """
        Verify Review (人工) and Feedback (机器) are completely independent.
        Review is stored in a different path, has different schema, different purpose.
        """
        from core.audit.review.decision_review import DecisionReviewManager
        from core.audit.schemas.review import Review

        with tempfile.TemporaryDirectory() as rev_tmp, tempfile.TemporaryDirectory() as fb_tmp:
            review_mgr = DecisionReviewManager(base_path=rev_tmp)
            reg = FeedbackRegistry(base_path=fb_tmp)

            # Create a Review (人工)
            review = review_mgr.create(audit_id="dr-test-001", reviewer="alvin")
            assert review.review_type == "decision"
            assert review.status.value == "pending"

            # Create a Feedback (机器)
            from core.audit.schemas.feedback import Feedback
            fb = Feedback(
                feedback_id="fb-test-001",
                feedback_type=FeedbackType.SIGNAL_DECAY,
                severity="medium",
                sample_size=10,
                evidence={},
                metric_name="signal_age_pnl_pct",
                metric_value=-0.01,
                status=FeedbackStatus.PENDING,
            )
            reg.append(fb)

            # They are stored separately, different schemas, different purposes
            review_pending = review_mgr.list_pending()
            fb_pending = reg.read_unprocessed()

            assert len(review_pending) == 1
            assert len(fb_pending) == 1
            # Different IDs
            assert review_pending[0].review_id != fb_pending[0].feedback_id
            # Different status enums (both PENDING but different types)
            assert review_pending[0].status.value == "pending"
            assert fb_pending[0].status.value == "pending"
            # Review has verdict/accuracy_score, Feedback does not
            assert hasattr(review_pending[0], "accuracy_score")
            assert not hasattr(fb_pending[0], "accuracy_score")

    def test_audit_record_not_modified_after_ingest(self) -> None:
        """Append-only: ingested audit records must not be mutated by later steps."""
        dec_auditor = DecisionAuditor()
        record = dec_auditor.ingest(
            FakeArbitrationDecision(
                decision_id="d-immut-001",
                symbol="AAPL",
                bias="long_bias",
                confidence=0.8,
                target_direction="LONG",
                target_quantity=500.0,
                source_signals=[],
            ),
        )
        original_audit_id = record.audit_id
        original_timestamp = record.timestamp

        # Simulate later steps that might mutate the record
        fb_engine = FeedbackEngine()
        feedbacks = fb_engine.scan([record], [], [])
        for fb in feedbacks:
            fb.severity = "high"

        # Record itself must not be modified
        assert record.audit_id == original_audit_id
        assert record.timestamp == original_timestamp
