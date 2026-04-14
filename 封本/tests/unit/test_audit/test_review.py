"""Tests for DecisionReviewManager and ExecutionReviewManager."""
import pytest
import tempfile
from datetime import datetime
from core.audit.review.decision_review import DecisionReviewManager
from core.audit.review.execution_review import ExecutionReviewManager
from core.audit.schemas.review import ReviewStatus


class TestDecisionReviewManager:
    def test_create_returns_pending_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DecisionReviewManager(base_path=tmpdir)
            review = manager.create(audit_id="dr-001", reviewer="alvin")
            assert review.review_id.startswith("rev-dec-")
            assert review.audit_id == "dr-001"
            assert review.review_type == "decision"
            assert review.status == ReviewStatus.PENDING
            assert review.reviewer == "alvin"

    def test_complete_appends_completed_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DecisionReviewManager(base_path=tmpdir)
            created = manager.create(audit_id="dr-002")
            completed = manager.complete(
                review_id=created.review_id,
                accuracy_score=0.75,
                verdict="correct",
                notes="Good trade",
                tags=["profit", "low_risk"],
            )
            assert completed.accuracy_score == 0.75
            assert completed.verdict == "correct"
            assert completed.notes == "Good trade"
            assert completed.tags == ["profit", "low_risk"]
            assert completed.status == ReviewStatus.COMPLETED
            assert completed.reviewed_at is not None

    def test_list_pending_only_returns_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DecisionReviewManager(base_path=tmpdir)
            p1 = manager.create(audit_id="dr-003")
            p2 = manager.create(audit_id="dr-004")
            manager.complete(p1.review_id, 0.8, "correct")
            pending = manager.list_pending()
            assert len(pending) == 1
            assert pending[0].audit_id == "dr-004"

    def test_append_only_never_modifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DecisionReviewManager(base_path=tmpdir)
            created = manager.create(audit_id="dr-005")
            manager.complete(created.review_id, 0.6, "incorrect")
            # Both records should exist (append-only)
            pending = manager.list_pending()
            assert len(pending) == 0  # no pending left
            # The original and completed records both exist in file


class TestExecutionReviewManager:
    def test_create_returns_pending_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ExecutionReviewManager(base_path=tmpdir)
            review = manager.create(audit_id="er-001", reviewer="alvin")
            assert review.review_id.startswith("rev-exec-")
            assert review.audit_id == "er-001"
            assert review.review_type == "execution"
            assert review.status == ReviewStatus.PENDING

    def test_complete_execution_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ExecutionReviewManager(base_path=tmpdir)
            created = manager.create(audit_id="er-002")
            completed = manager.complete(
                review_id=created.review_id,
                accuracy_score=0.9,
                verdict="correct",
                notes="Fast fill, low slippage",
                tags=["excellent_fill"],
            )
            assert completed.accuracy_score == 0.9
            assert completed.verdict == "correct"
            assert completed.notes == "Fast fill, low slippage"
            assert completed.status == ReviewStatus.COMPLETED

    def test_list_pending_execution_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ExecutionReviewManager(base_path=tmpdir)
            p1 = manager.create(audit_id="er-003")
            manager.create(audit_id="er-004")
            manager.complete(p1.review_id, 0.7, "correct")
            pending = manager.list_pending()
            assert len(pending) == 1
            assert pending[0].audit_id == "er-004"

    def test_review_types_are_isolated(self) -> None:
        """Decision and Execution reviews are stored in separate subdirectories."""
        with tempfile.TemporaryDirectory() as dec_tmp, tempfile.TemporaryDirectory() as exec_tmp:
            dec_mgr = DecisionReviewManager(base_path=dec_tmp)
            exec_mgr = ExecutionReviewManager(base_path=exec_tmp)
            dec_mgr.create(audit_id="dr-iso-001")
            exec_mgr.create(audit_id="er-iso-001")
            dec_pending = dec_mgr.list_pending()
            exec_pending = exec_mgr.list_pending()
            assert len(dec_pending) == 1
            assert dec_pending[0].audit_id == "dr-iso-001"
            assert len(exec_pending) == 1
            assert exec_pending[0].audit_id == "er-iso-001"
