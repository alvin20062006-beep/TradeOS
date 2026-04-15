"""Tests for FeedbackRegistry."""
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from core.audit.closed_loop.feedback_registry import FeedbackRegistry
from core.audit.schemas.feedback import Feedback, FeedbackType, FeedbackStatus


class TestFeedbackRegistry:
    def test_append_and_read_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FeedbackRegistry(base_path=tmpdir)
            fb = Feedback(
                feedback_id="fb-test-001",
                feedback_type=FeedbackType.SLIPPAGE_CALIBRATION,
                severity="high",
                symbol="AAPL",
                sample_size=50,
                evidence={"bias_bps": 8.2},
                metric_name="slippage_bias_bps",
                metric_value=8.2,
                threshold_breach=True,
                suggested_action="adjust slippage model",
                confidence=0.85,
                status=FeedbackStatus.PENDING,
            )
            registry.append(fb)

            all_fb = registry.read_all()
            assert len(all_fb) == 1
            assert all_fb[0].feedback_id == "fb-test-001"
            assert all_fb[0].severity == "high"
            assert all_fb[0].evidence["bias_bps"] == 8.2

    def test_append_many(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FeedbackRegistry(base_path=tmpdir)
            fbs = [
                Feedback(
                    feedback_id=f"fb-multi-{i}",
                    feedback_type=FeedbackType.FILTER_PATTERN,
                    severity="medium",
                    sample_size=20,
                    evidence={"veto_rate": 0.35},
                    metric_name="filter_veto_rate",
                    metric_value=0.35,
                    status=FeedbackStatus.PENDING,
                )
                for i in range(3)
            ]
            registry.append_many(fbs)

            all_fb = registry.read_all()
            assert len(all_fb) == 3

    def test_read_unprocessed(self) -> None:
        """read_unprocessed 只返回 PENDING，已 reviewed/rejected 的不出现。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FeedbackRegistry(base_path=tmpdir)
            pending = Feedback(
                feedback_id="fb-pending",
                feedback_type=FeedbackType.SIGNAL_DECAY,
                severity="high",
                sample_size=10,
                evidence={},
                metric_name="signal_age_pnl_pct",
                metric_value=-0.015,
                status=FeedbackStatus.PENDING,
            )
            reviewed = Feedback(
                feedback_id="fb-reviewed",
                feedback_type=FeedbackType.SLIPPAGE_CALIBRATION,
                severity="low",
                sample_size=30,
                evidence={},
                metric_name="slippage_bias_bps",
                metric_value=1.0,
                status=FeedbackStatus.REVIEWED,
            )
            registry.append(pending)
            registry.append(reviewed)

            unprocessed = registry.read_unprocessed()
            ids = [f.feedback_id for f in unprocessed]
            # REVIEWED items excluded from read_unprocessed (append-only + deduplication)
            assert "fb-pending" in ids
            assert "fb-reviewed" not in ids

    def test_mark_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FeedbackRegistry(base_path=tmpdir)
            fb = Feedback(
                feedback_id="fb-review-me",
                feedback_type=FeedbackType.FACTOR_ATTRIBUTION,
                severity="medium",
                sample_size=40,
                evidence={},
                metric_name="factor_ir",
                metric_value=0.15,
                status=FeedbackStatus.PENDING,
            )
            registry.append(fb)
            registry.mark_reviewed("fb-review-me", "alvin")

            all_fb = registry.read_all()
            # Both original (pending) and updated (reviewed) are stored
            assert len(all_fb) == 2
            reviewed = [f for f in all_fb if f.feedback_id == "fb-review-me" and f.status == FeedbackStatus.REVIEWED]
            assert len(reviewed) == 1
            assert reviewed[0].reviewed_by == "alvin"

    def test_mark_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FeedbackRegistry(base_path=tmpdir)
            fb = Feedback(
                feedback_id="fb-reject-me",
                feedback_type=FeedbackType.SLIPPAGE_CALIBRATION,
                severity="low",
                sample_size=10,
                evidence={},
                metric_name="slippage_bias_bps",
                metric_value=1.5,
                status=FeedbackStatus.PENDING,
            )
            registry.append(fb)
            registry.mark_rejected("fb-reject-me", "alvin", "model already calibrated")

            all_fb = registry.read_all()
            rejected = [f for f in all_fb if f.status == FeedbackStatus.REJECTED]
            assert len(rejected) == 1
            assert rejected[0].rejection_reason == "model already calibrated"
