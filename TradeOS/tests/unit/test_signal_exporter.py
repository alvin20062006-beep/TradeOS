"""
test_signal_exporter.py — SignalExporter + DeploymentExporter Unit Tests
=======================================================================
Tests C4 constraint and export functionality.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pandas as pd
import pytest

from core.research.deployment.candidates import (
    DeploymentExporter,
    SignalExporter,
    _EXECUTION_LAYER_FIELDS,
)
from core.research.models import (
    DeploymentCandidate,
    ResearchExperimentRecord,
    ModelArtifact,
    SignalCandidate,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def predictions_df() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame({
        "symbol": ["AAPL", "MSFT", "GOOG", "AMZN", "META"],
        "timestamp": dates,
        "score": [0.05, -0.03, 0.02, -0.01, 0.07],
        "label": [0.01, -0.01, 0.005, -0.005, 0.015],
    })


@pytest.fixture
def experiment_record() -> ResearchExperimentRecord:
    return ResearchExperimentRecord(
        experiment_id="exp_sig_test_001",
        name="test_signal_export",
        dataset_version="ds_test",
        feature_set_version="fsv_test",
        label_set_version="lsv_test",
        model_name="ridge",
        model_params={"model_type": "ridge"},
        train_start=datetime(2023, 1, 1),
        train_end=datetime(2023, 12, 31),
        valid_start=datetime(2024, 1, 1),
        valid_end=datetime(2024, 6, 30),
        test_start=datetime(2024, 7, 1),
        test_end=datetime(2024, 12, 31),
        status="completed",
        metrics={"ic": 0.05, "rank_ic": 0.04, "sharpe": 0.8, "max_drawdown": 0.10},
    )


@pytest.fixture
def model_artifact(experiment_record: ResearchExperimentRecord) -> ModelArtifact:
    return ModelArtifact(
        artifact_id="art_sig_test_001",
        experiment_id=experiment_record.experiment_id,
        model_name="ridge",
        model_type="ridge",
        version="1.0.0",
        path="/tmp/test_model.pkl",
        feature_names=["RET_1d", "RSI_14"],
        label_name="label",
        metrics_snapshot={"ic": 0.05},
    )


# ── S1: SignalExporter ─────────────────────────────────────────

class TestSignalExporter:
    """S1: SignalExporter tests."""

    def test_s1_returns_list(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        exporter = SignalExporter()
        signals = exporter.from_predictions(
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
            predictions=predictions_df,
        )

        assert isinstance(signals, list)
        assert len(signals) == len(predictions_df)
        assert all(isinstance(s, SignalCandidate) for s in signals)

    def test_s1_top_n(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        exporter = SignalExporter()
        signals = exporter.from_predictions(
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
            predictions=predictions_df,
            top_n=2,
        )

        assert len(signals) == 2

    def test_s1_direction_hint(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        exporter = SignalExporter()
        signals = exporter.from_predictions(
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
            predictions=predictions_df,
        )

        # Positive score + positive label → long
        # META has highest positive score
        top_signal = max(signals, key=lambda s: s.score)
        assert top_signal.direction_hint == "long"

    def test_s1_confidence_bounds(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        exporter = SignalExporter()
        signals = exporter.from_predictions(
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
            predictions=predictions_df,
        )

        for s in signals:
            assert 0.0 <= s.confidence <= 1.0

    def test_s1_json_roundtrip(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
        tmp_path: pytest(tmp_path),
    ):
        exporter = SignalExporter(export_dir=tmp_path)
        signals = exporter.from_predictions(
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
            predictions=predictions_df,
            top_n=3,
        )

        path = exporter.to_json(signals, experiment_id=experiment_record.experiment_id)

        assert path.exists()
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        assert payload["experiment_id"] == experiment_record.experiment_id
        assert payload["signal_count"] == 3
        assert len(payload["signals"]) == 3


# ── S2: C4 constraint ──────────────────────────────────────────

class TestC4Constraint:
    """S2: SignalCandidate must NOT contain execution-layer fields."""

    def test_s2_execution_layer_fields_not_in_metadata(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        """
        C4 constraint: SignalCandidate must NOT have execution-layer fields.
        This test verifies that _EXECUTION_LAYER_FIELDS is not violated.
        """
        exporter = SignalExporter()
        signals = exporter.from_predictions(
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
            predictions=predictions_df,
        )

        violations: list[str] = []
        for sig in signals:
            # Check top-level fields
            for field in _EXECUTION_LAYER_FIELDS:
                val = getattr(sig, field, None)
                if val is not None and field not in {"score", "confidence"}:
                    violations.append(f"{sig.candidate_id}.{field} = {val}")

            # Check metadata
            for field in _EXECUTION_LAYER_FIELDS:
                if field in (sig.metadata or {}):
                    violations.append(f"{sig.candidate_id}.metadata[{field!r}]")

        assert violations == [], f"C4 violations: {violations}"

    def test_s2_validate_schema_raises_on_violation(self):
        """
        validate_schema() must raise ValueError if execution-layer fields are found.
        """
        # Manually create a violating SignalCandidate
        sig = SignalCandidate(
            candidate_id="sig_violate",
            experiment_id="exp_001",
            model_artifact_id="art_001",
            symbol="AAPL",
            timestamp=datetime.now(),
            score=0.05,
            direction_hint="long",
            confidence=0.7,
            horizon=1,
            # These are RESEARCH-layer fields — fine
            score_normalized=0.5,
        )

        exporter = SignalExporter()
        # Should not raise (no execution-layer fields present)
        exporter.validate_schema([sig])

        # Now check with a real test: simulate violation via metadata
        sig_bad = SignalCandidate(
            candidate_id="sig_bad",
            experiment_id="exp_001",
            model_artifact_id="art_001",
            symbol="AAPL",
            timestamp=datetime.now(),
            score=0.05,
            direction_hint="long",
            confidence=0.7,
            horizon=1,
            metadata={"stop_loss": 0.05, "position_size": 1000},  # Execution-layer fields
        )

        with pytest.raises(ValueError, match="C4 constraint violation"):
            exporter.validate_schema([sig_bad])


# ── D1/D2: DeploymentExporter ─────────────────────────────────

class TestDeploymentExporter:
    """D1/D2: DeploymentExporter tests."""

    def test_d1_returns_deployment_candidate(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        signals = [
            SignalCandidate(
                candidate_id="sig_1",
                experiment_id=experiment_record.experiment_id,
                model_artifact_id=model_artifact.artifact_id,
                symbol="AAPL",
                timestamp=datetime.now(),
                score=0.05,
                direction_hint="long",
                confidence=0.7,
                horizon=1,
            )
        ]

        exporter = DeploymentExporter()
        deployment = exporter.from_experiment(
            experiment=experiment_record,
            model_artifact=model_artifact,
            signals=signals,
        )

        assert isinstance(deployment, DeploymentCandidate)
        assert deployment.approval_status == "pending", "D2: approval_status must be 'pending'"
        assert deployment.deployment_id is not None
        assert deployment.experiment_id == experiment_record.experiment_id

    def test_d2_metrics_snapshot_in_deployment(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        """D2: DeploymentCandidate must contain metrics_snapshot."""
        signals = [
            SignalCandidate(
                candidate_id="sig_1",
                experiment_id=experiment_record.experiment_id,
                model_artifact_id=model_artifact.artifact_id,
                symbol="AAPL",
                timestamp=datetime.now(),
                score=0.05,
                direction_hint="long",
                confidence=0.7,
                horizon=1,
            )
        ]

        exporter = DeploymentExporter()
        deployment = exporter.from_experiment(
            experiment=experiment_record,
            model_artifact=model_artifact,
            signals=signals,
        )

        # D2: metrics_snapshot must be present and non-empty
        assert isinstance(deployment.metrics_snapshot, dict)
        assert "ic" in deployment.metrics_snapshot or "sharpe" in deployment.metrics_snapshot

    def test_d2_comparison_to_baseline(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        signals = [
            SignalCandidate(
                candidate_id="sig_1",
                experiment_id=experiment_record.experiment_id,
                model_artifact_id=model_artifact.artifact_id,
                symbol="AAPL",
                timestamp=datetime.now(),
                score=0.05,
                direction_hint="long",
                confidence=0.7,
                horizon=1,
            )
        ]
        baseline = {"ic": 0.03, "sharpe": 0.5}

        exporter = DeploymentExporter()
        deployment = exporter.from_experiment(
            experiment=experiment_record,
            model_artifact=model_artifact,
            signals=signals,
            baseline_metrics=baseline,
        )

        assert "delta_ic" in deployment.comparison_to_baseline
        assert "delta_sharpe" in deployment.comparison_to_baseline

    def test_d1_validate_schema(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        signals = [
            SignalCandidate(
                candidate_id="sig_1",
                experiment_id=experiment_record.experiment_id,
                model_artifact_id=model_artifact.artifact_id,
                symbol="AAPL",
                timestamp=datetime.now(),
                score=0.05,
                direction_hint="long",
                confidence=0.7,
                horizon=1,
            )
        ]

        exporter = DeploymentExporter()
        deployment = exporter.from_experiment(
            experiment=experiment_record,
            model_artifact=model_artifact,
            signals=signals,
        )

        # validate_schema should not raise for valid deployment
        exporter.validate_schema(deployment)

    def test_d1_invalid_approval_status_raises(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        signals = [
            SignalCandidate(
                candidate_id="sig_1",
                experiment_id=experiment_record.experiment_id,
                model_artifact_id=model_artifact.artifact_id,
                symbol="AAPL",
                timestamp=datetime.now(),
                score=0.05,
                direction_hint="long",
                confidence=0.7,
                horizon=1,
            )
        ]

        exporter = DeploymentExporter()
        deployment = exporter.from_experiment(
            experiment=experiment_record,
            model_artifact=model_artifact,
            signals=signals,
        )

        # Manually set invalid status to test validation
        deployment.approval_status = "invalid_status"  # type: ignore

        with pytest.raises(ValueError, match="Invalid approval_status"):
            exporter.validate_schema(deployment)

    def test_d1_json_roundtrip(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
        tmp_path: pytest(tmp_path),
    ):
        signals = [
            SignalCandidate(
                candidate_id="sig_1",
                experiment_id=experiment_record.experiment_id,
                model_artifact_id=model_artifact.artifact_id,
                symbol="AAPL",
                timestamp=datetime.now(),
                score=0.05,
                direction_hint="long",
                confidence=0.7,
                horizon=1,
            )
        ]

        exporter = DeploymentExporter(export_dir=tmp_path)
        deployment = exporter.from_experiment(
            experiment=experiment_record,
            model_artifact=model_artifact,
            signals=signals,
        )

        path = exporter.to_json(deployment)
        assert path.exists()
