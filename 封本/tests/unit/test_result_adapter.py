"""
test_result_adapter.py — ResultAdapter Unit Tests
================================================
Tests ResultAdapter's four responsibility areas:
    R1: predictions_to_signals()
    R2: experiment_to_artifact()
    R3: experiment_to_deployment()
    R4: evaluation_to_metrics()
"""

from __future__ import annotations

# FakeModel is defined at module level in conftest.py
from tests.conftest import FakeModel

from pathlib import Path
import pickle
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from core.research.models import (
    DeploymentCandidate,
    ResearchExperimentRecord,
    ModelArtifact,
    SignalCandidate,
)
from core.research.qlib.result_adapter import ResultAdapter


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def predictions_df() -> pd.DataFrame:
    """
    5 symbols × 3 timestamps = 15 rows.
    Columns: symbol, timestamp, score, label
    """
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    symbols = ["AAPL", "MSFT", "GOOG", "AMZN", "META"]

    rows = []
    for sym in symbols:
        for i, d in enumerate(dates):
            # Score correlates weakly with label
            label = 0.01 if i % 2 == 0 else -0.01
            score = label * 1.5 + 0.001
            rows.append({"symbol": sym, "timestamp": d, "score": score, "label": label})

    return pd.DataFrame(rows)


@pytest.fixture
def returns_series() -> pd.Series:
    """Daily returns series for evaluation."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    np.random.seed(42)
    return pd.Series(
        np.random.normal(0.001, 0.02, size=30),
        index=dates,
        name="return",
    )


@pytest.fixture
def eval_df() -> pd.DataFrame:
    """Evaluation DataFrame with return column."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    np.random.seed(42)
    return pd.DataFrame({
        "timestamp": dates,
        "return": np.random.normal(0.001, 0.02, size=30),
        "label": np.random.choice([0.0, 1.0], size=30),
    })


@pytest.fixture
def experiment_record() -> ResearchExperimentRecord:
    return ResearchExperimentRecord(
        experiment_id="exp_test_001",
        name="test_experiment",
        dataset_version="ds_test_001",
        feature_set_version="fsv_test_001",
        label_set_version="lsv_test_001",
        model_name="ridge",
        model_params={"model_type": "ridge", "alpha": 1.0},
        train_start=datetime(2023, 1, 1),
        train_end=datetime(2023, 12, 31),
        valid_start=datetime(2024, 1, 1),
        valid_end=datetime(2024, 6, 30),
        test_start=datetime(2024, 7, 1),
        test_end=datetime(2024, 12, 31),
        status="completed",
        metrics={
            "ic": 0.05,
            "rank_ic": 0.04,
            "sharpe": 0.8,
            "max_drawdown": 0.10,
            "hit_rate": 0.55,
            "calmar": 0.6,
        },
    )


@pytest.fixture
def model_artifact(experiment_record: ResearchExperimentRecord, tmp_path: pytest(tmp_path)) -> ModelArtifact:
    """A model artifact with a real pickle file."""
    import_path = tmp_path / "model.pkl"

    with open(import_path, "wb") as f:
        pickle.dump(FakeModel(), f)

    return ModelArtifact(
        artifact_id="art_test_001",
        experiment_id=experiment_record.experiment_id,
        model_name="ridge",
        model_type="ridge",
        version="1.0.0",
        path=str(import_path),
        feature_names=["RET_1d", "RSI_14"],
        label_name="label",
        metrics_snapshot={"ic": 0.05, "sharpe": 0.8},
    )


# ── R1: predictions -> SignalCandidate ─────────────────────────

class TestPredictionsToSignals:
    """R1: predictions_to_signals() tests."""

    def test_r1_returns_list_of_signal_candidates(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        adapter = ResultAdapter()
        signals = adapter.predictions_to_signals(
            predictions=predictions_df,
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
        )

        assert isinstance(signals, list)
        assert len(signals) == len(predictions_df)
        assert all(isinstance(s, SignalCandidate) for s in signals)

    def test_r1_direction_hint_long(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        # Positive score + positive label → long
        df = predictions_df.copy()
        df["score"] = 0.05
        df["label"] = 0.01

        adapter = ResultAdapter()
        signals = adapter.predictions_to_signals(df, experiment_record.experiment_id, model_artifact.artifact_id)

        assert all(s.direction_hint == "long" for s in signals)

    def test_r1_direction_hint_short(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        # Negative score → short
        df = pd.DataFrame({
            "symbol": ["A"],
            "timestamp": [datetime(2024, 1, 1)],
            "score": [-0.05],
            "label": [-0.01],
        })

        adapter = ResultAdapter()
        signals = adapter.predictions_to_signals(df, experiment_record.experiment_id, model_artifact.artifact_id)

        assert all(s.direction_hint == "short" for s in signals)

    def test_r1_top_n(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        adapter = ResultAdapter()
        signals = adapter.predictions_to_signals(
            predictions=predictions_df,
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
            top_n=3,
        )

        assert len(signals) == 3

    def test_r1_confidence_normalized(
        self,
        predictions_df: pd.DataFrame,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        adapter = ResultAdapter()
        signals = adapter.predictions_to_signals(
            predictions=predictions_df,
            experiment_id=experiment_record.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
        )

        assert all(0.0 <= s.confidence <= 1.0 for s in signals)

    def test_r1_missing_required_column_raises(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        df = pd.DataFrame({"symbol": ["A"], "timestamp": [datetime.now()]})  # missing score

        adapter = ResultAdapter()
        with pytest.raises(ValueError, match="missing required columns"):
            adapter.predictions_to_signals(df, experiment_record.experiment_id, model_artifact.artifact_id)


# ── R2: experiment + model info -> ModelArtifact ─────────────

class TestExperimentToArtifact:
    """R2: experiment_to_artifact() tests."""

    def test_r2_returns_model_artifact(
        self,
        experiment_record: ResearchExperimentRecord,
    ):
        adapter = ResultAdapter()
        artifact = adapter.experiment_to_artifact(
            experiment=experiment_record,
            model_object=FakeModel(),
            feature_names=["RET_1d", "RSI_14"],
        )

        assert isinstance(artifact, ModelArtifact)
        assert artifact.artifact_id is not None
        assert artifact.experiment_id == experiment_record.experiment_id
        assert artifact.model_name == "ridge"
        assert artifact.feature_names == ["RET_1d", "RSI_14"]

    def test_r2_persists_pickle(
        self,
        experiment_record: ResearchExperimentRecord,
        tmp_path: pytest(tmp_path),
    ):
        adapter = ResultAdapter(model_save_dir=tmp_path)
        artifact = adapter.experiment_to_artifact(
            experiment=experiment_record,
            model_object=FakeModel(),
        )

        import_path = Path(artifact.path)
        assert import_path.exists(), f"Pickle file not written to {import_path}"

    def test_r2_load_model_roundtrip(
        self,
        experiment_record: ResearchExperimentRecord,
        tmp_path: pytest(tmp_path),
    ):
        adapter = ResultAdapter(model_save_dir=tmp_path)
        artifact = adapter.experiment_to_artifact(
            experiment=experiment_record,
            model_object=FakeModel(),
        )

        loaded = adapter.load_model(artifact)
        assert isinstance(loaded, FakeModel)
        assert loaded.coefficient == 1.5


# ── R3: experiment -> DeploymentCandidate ─────────────────────

class TestExperimentToDeployment:
    """R3: experiment_to_deployment() tests."""

    def test_r3_returns_deployment_candidate(
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

        adapter = ResultAdapter()
        deployment = adapter.experiment_to_deployment(
            experiment=experiment_record,
            signals=signals,
            model_artifact=model_artifact,
        )

        assert isinstance(deployment, DeploymentCandidate)
        assert deployment.approval_status == "pending"
        assert deployment.experiment_id == experiment_record.experiment_id

    def test_r3_comparison_to_baseline(
        self,
        experiment_record: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
    ):
        baseline = {"ic": 0.03, "sharpe": 0.5}
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

        adapter = ResultAdapter()
        deployment = adapter.experiment_to_deployment(
            experiment=experiment_record,
            signals=signals,
            model_artifact=model_artifact,
            baseline_metrics=baseline,
        )

        assert "delta_ic" in deployment.comparison_to_baseline
        assert "delta_sharpe" in deployment.comparison_to_baseline

    def test_r3_symbols_from_signals(
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
            ),
            SignalCandidate(
                candidate_id="sig_2",
                experiment_id=experiment_record.experiment_id,
                model_artifact_id=model_artifact.artifact_id,
                symbol="MSFT",
                timestamp=datetime.now(),
                score=-0.03,
                direction_hint="short",
                confidence=0.6,
                horizon=1,
            ),
        ]

        adapter = ResultAdapter()
        deployment = adapter.experiment_to_deployment(
            experiment=experiment_record,
            signals=signals,
            model_artifact=model_artifact,
        )

        assert set(deployment.symbols) == {"AAPL", "MSFT"}


# ── R4: evaluation -> internal metrics dict ───────────────────

class TestEvaluationToMetrics:
    """R4: evaluation_to_metrics() tests."""

    def test_r4_returns_all_keys(
        self,
        predictions_df: pd.DataFrame,
        returns_series: pd.Series,
    ):
        adapter = ResultAdapter()
        metrics = adapter.evaluation_to_metrics(
            predictions=predictions_df,
            returns=returns_series,
        )

        expected_keys = {"ic", "rank_ic", "sharpe", "max_drawdown", "hit_rate", "calmar"}
        assert expected_keys.issubset(metrics.keys()), f"Missing keys: {expected_keys - set(metrics.keys())}"

    def test_r4_all_values_float(
        self,
        predictions_df: pd.DataFrame,
        returns_series: pd.Series,
    ):
        adapter = ResultAdapter()
        metrics = adapter.evaluation_to_metrics(predictions_df, returns_series)

        assert all(isinstance(v, (int, float)) for v in metrics.values())

    def test_r4_from_eval_df(
        self,
        predictions_df: pd.DataFrame,
        eval_df: pd.DataFrame,
    ):
        adapter = ResultAdapter()
        metrics = adapter.evaluation_to_metrics_from_df(
            predictions=predictions_df,
            eval_df=eval_df,
        )

        expected_keys = {"ic", "rank_ic", "sharpe", "max_drawdown", "hit_rate", "calmar"}
        assert expected_keys.issubset(metrics.keys())
