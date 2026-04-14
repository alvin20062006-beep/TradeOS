"""
Alpha Factor Schema Definitions
===============================
Five core objects:
    AlphaFactorSpec      - metadata for a factor definition
    AlphaFactorValue     - raw + normalized values per symbol-timestamp
    AlphaFactorSet       - a curated set of factors with pre-processing config
    AlphaValidationResult - quality checks (coverage, null, constant, outlier, leakage)
    CompositeFactor      - L3 multi-factor combination
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# AlphaFactorSpec
# ─────────────────────────────────────────────────────────────────


class AlphaFactorSpec(BaseModel):
    """
    Metadata definition for an alpha factor.

    Produced by the six analysis modules; standardized and registered
    by the alpha layer.
    """

    factor_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    factor_name: str
    factor_group: str  # technical / fundamental / macro / sentiment / orderflow
    source_module: str  # analysis.technical / analysis.fundamental / etc.

    # Human-readable formula description
    formula_description: str = ""
    python_expression: Optional[str] = None

    # Input / output contracts
    input_fields: list[str] = Field(default_factory=list)  # e.g. ["close", "high", "low"]
    output_type: Literal["float", "int", "bool", "categorical"] = "float"

    # Factor-specific parameters
    parameters: dict[str, Any] = Field(default_factory=dict)  # e.g. {"period": 14}

    # Layer: L1 = raw, L2 = normalized (always "L1" here; L2/L3 are separate specs)
    layer: Literal["L1", "L2", "L3"] = "L1"

    version: str = "1.0.0"  # semver
    parent_factor_id: Optional[str] = None  # for parameter-variant tracking

    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"

    description: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# AlphaFactorValue
# ─────────────────────────────────────────────────────────────────


class AlphaFactorValue(BaseModel):
    """
    A single factor value for one symbol at one timestamp.

    Stores both raw (L1) and normalized (L2) values.
    """

    value_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    factor_id: str

    symbol: str
    timestamp: datetime
    frequency: str = "1D"

    # L1: raw value (always present)
    raw_value: float

    # L2: normalized value (populated after normalization step)
    normalized_value: Optional[float] = None

    # Quality flag
    is_valid: bool = True
    invalid_reason: Optional[str] = None

    # Context snapshot (optional)
    context_window: Optional[dict[str, float]] = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# AlphaFactorSet
# ─────────────────────────────────────────────────────────────────


class AlphaFactorSet(BaseModel):
    """
    A curated collection of factors with pre-processing configuration.

    This is the unit exported to Qlib as a FeatureSetVersion.
    """

    factor_set_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str

    # Factor IDs (referenced)
    factor_ids: list[str] = Field(default_factory=list)
    # Inline copies of specs for convenience (optional)
    factor_specs: list[AlphaFactorSpec] = Field(default_factory=list)

    # L2 pre-processing
    normalization_method: Literal["none", "winsorize", "zscore", "rank"] = "zscore"
    neutralization_method: Literal["none", "sector", "market"] = "none"

    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.now)

    # Statistical summary (populated after validation)
    coverage_summary: dict[str, float] = Field(default_factory=dict)   # factor_id -> rate
    ic_summary: dict[str, float] = Field(default_factory=dict)           # factor_id -> IC

    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# AlphaValidationResult
# ─────────────────────────────────────────────────────────────────


class AlphaValidationResult(BaseModel):
    """
    Executable quality checks for a factor.

    All fields are computed values, not schema placeholders.
    """

    factor_id: str
    factor_set_id: Optional[str] = None

    # ── Quality metrics (computed, not optional) ──
    coverage: float = 0.0        # fraction of non-null values, threshold > 0.9
    null_ratio: float = 0.0     # fraction of null/NaN, threshold < 0.1
    constant_ratio: float = 0.0  # fraction of constant values, threshold < 0.05
    outlier_ratio: float = 0.0   # fraction beyond 3-sigma / IQR, threshold < 0.05

    # ── Diagnostic flags ──
    correlation_warning: bool = False   # > 0.9 correlation with existing factors
    leakage_warning: bool = False       # suspiciously high contemporaneous correlation

    # ── Derived stats ──
    mean: Optional[float] = None
    std: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None

    # ── Gate ──
    is_qualified: bool = False
    fail_reasons: list[str] = Field(default_factory=list)

    # ── Eval window ──
    eval_start: Optional[datetime] = None
    eval_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# CompositeFactor
# ─────────────────────────────────────────────────────────────────


class CompositeFactor(BaseModel):
    """
    L3: A multi-factor combination output as a single signal.

    Has its own factor_id and version, treated as an independent factor.
    """

    factor_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    factor_name: str
    factor_group: str = "composite"
    source_module: str = "alpha.builders.composite"

    formula_description: str = ""
    layer: Literal["L1", "L2", "L3"] = "L3"

    # Component factors
    component_factor_ids: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)  # factor_id -> weight

    # Combination method
    combination_method: Literal["weighted", "pca", "ic_weighted", "equal"] = "equal"

    parameters: dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"

    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
