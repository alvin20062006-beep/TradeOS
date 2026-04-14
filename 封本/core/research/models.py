"""
Research layer core schema definitions.

These schemas define the internal research objects used throughout the
research factory. Qlib-native objects must never be exposed directly;
all outputs are converted to these types before leaving the research layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Dataset Schemas
# ─────────────────────────────────────────────────────────────────


class DatasetVersion(BaseModel):
    """
    A snapshot of a dataset build, used for experiment reproducibility.
    """

    dataset_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str = "1.0.0"  # semver

    symbols: list[str]
    frequency: str = "1D"  # 1D / 1H / 5min / 1min
    start_time: datetime
    end_time: datetime

    # Versioned dependencies
    feature_set_version: Optional[str] = None
    label_set_version: Optional[str] = None

    # Build metadata
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"

    source_provider: str = "unknown"  # yfinance / csv / polygon
    source_reference: str = ""

    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# Feature Schemas
# ─────────────────────────────────────────────────────────────────


class FeatureSetVersion(BaseModel):
    """
    A snapshot of a feature set build.
    """

    feature_set_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    feature_names: list[str] = Field(default_factory=list)
    feature_groups: dict[str, list[str]] = Field(default_factory=dict)

    version: str = "1.0.0"
    lookback_window: int = 20
    frequency: str = "1D"

    created_at: datetime = Field(default_factory=datetime.now)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    @property
    def feature_count(self) -> int:
        """Number of features in this feature set."""
        return len(self.feature_names)


# ─────────────────────────────────────────────────────────────────
# Label Schemas
# ─────────────────────────────────────────────────────────────────


class LabelSetVersion(BaseModel):
    """
    A snapshot of a label set build.
    """

    label_set_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    label_definitions: list[str] = Field(default_factory=list)

    horizon: int = 1
    horizon_unit: Literal["D", "H", "min"] = "D"

    label_type: Literal["regression", "classification", "multi_class"] = "regression"

    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.now)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# Experiment Schemas
# ─────────────────────────────────────────────────────────────────


class ResearchExperimentRecord(BaseModel):
    """
    A record of a complete research experiment run.

    This is the primary unit of tracking in the research registry.

    NOTE: Named ResearchExperimentRecord (not ExperimentRecord) to avoid
    naming conflict with Phase 1's core/schemas/ExperimentRecord, which
    has a different schema (general experiment tracking vs research factory).
    """

    experiment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str

    # Versioned dependencies
    dataset_version: str
    feature_set_version: Optional[str] = None
    label_set_version: Optional[str] = None

    # Model configuration
    model_name: str
    model_params: dict[str, Any] = Field(default_factory=dict)

    # Training windows
    train_start: Optional[datetime] = None
    train_end: Optional[datetime] = None
    valid_start: Optional[datetime] = None
    valid_end: Optional[datetime] = None
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None

    # Timestamps
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"

    # Evaluation results
    metrics: dict[str, float] = Field(default_factory=dict)

    # Artifacts
    artifacts: list[str] = Field(default_factory=list)

    notes: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# Model Artifact Schemas
# ─────────────────────────────────────────────────────────────────


class ModelArtifact(BaseModel):
    """
    A trained model artifact produced by an experiment.
    """

    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str

    model_name: str
    model_type: str  # lightgbm / dnn / catboost

    version: str
    path: str  # local filesystem path
    uri: Optional[str] = None  # S3 / cloud URI

    # Training metadata
    feature_names: list[str] = Field(default_factory=list)
    label_name: str = "label"
    train_symbols: list[str] = Field(default_factory=list)

    # Evaluation snapshot at training time
    metrics_snapshot: dict[str, float] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# Signal / Deployment Schemas
# ─────────────────────────────────────────────────────────────────


class SignalCandidate(BaseModel):
    """
    A research-layer signal candidate exported to the arbitration layer.

    Phase 4 scope:
        - score, direction_hint, confidence, horizon, experiment_id
        - NO execution-layer fields (order_type, execution_algo,
          position_size, stop_loss, take_profit)
    """

    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str
    model_artifact_id: str

    symbol: str
    timestamp: datetime

    # Research-layer semantics
    score: float
    score_normalized: Optional[float] = None

    direction_hint: Literal["long", "short", "neutral"] = "neutral"
    confidence: float = Field(ge=0.0, le=1.0)

    horizon: int = 1
    feature_snapshot: Optional[dict[str, float]] = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DeploymentCandidate(BaseModel):
    """
    A model ready for deployment review.

    Produced after an experiment passes quality gates.
    """

    deployment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str
    model_artifact_id: str

    # Approval workflow
    approval_status: Literal["pending", "approved", "rejected", "recalled"] = "pending"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # Performance snapshot
    metrics_snapshot: dict[str, float] = Field(default_factory=dict)
    comparison_to_baseline: dict[str, float] = Field(default_factory=dict)

    # Scope
    symbols: list[str] = Field(default_factory=list)
    valid_from: datetime
    valid_until: Optional[datetime] = None

    notes: str = ""
    exported_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
