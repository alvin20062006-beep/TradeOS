"""
Label Schema Definitions
========================
Unified schema for all label modules.

Defines:
    LabelSpec    - Label definition metadata
    LabelResult  - Computed label result with series
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# LabelSpec
# ─────────────────────────────────────────────────────────────────


class LabelSpec(BaseModel):
    """
    Metadata definition for a label.

    Attributes
    ----------
    label_id : str
        Unique identifier.
    label_name : str
        Human-readable name (e.g., "return_5d", "direction_1d").
    label_type : str
        "regression" | "classification" | "ordinal".
    horizon : int
        Number of periods ahead.
    horizon_unit : str
        "D" | "H" | "min".
    description : str
        Human-readable description.
    parameters : dict
        Additional parameters (e.g., threshold for direction labels).
    """

    label_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label_name: str
    label_type: Literal["regression", "classification", "ordinal"] = "regression"
    horizon: int = 1
    horizon_unit: Literal["D", "H", "min"] = "D"
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────
# LabelResult
# ─────────────────────────────────────────────────────────────────


class LabelResult(BaseModel):
    """
    Computed label result.

    Attributes
    ----------
    spec : LabelSpec
        The label definition.
    series : pd.DataFrame
        Computed label values with columns: symbol, timestamp, label_value.
        Stored as dict for JSON serialization.
    metadata : dict
        Computation metadata (e.g., n_samples, coverage, mean, std).
    computed_at : datetime
        Time of computation.
    """

    spec: LabelSpec
    series: dict[str, Any] = Field(default_factory=dict)  # JSON-serializable DataFrame
    metadata: dict[str, Any] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    @classmethod
    def from_dataframe(
        cls,
        spec: LabelSpec,
        df: pd.DataFrame,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "LabelResult":
        """
        Create LabelResult from a DataFrame.

        Parameters
        ----------
        spec : LabelSpec
        df : pd.DataFrame
            Columns: symbol, timestamp, label_value
        metadata : dict, optional
        """
        # Convert DataFrame to dict for JSON serialization
        series_dict = df.to_dict(orient="list")

        # Compute basic stats
        if metadata is None:
            metadata = {}
        if "label_value" in df.columns:
            metadata["n_samples"] = len(df)
            metadata["coverage"] = 1.0 - df["label_value"].isna().mean()
            metadata["mean"] = float(df["label_value"].mean())
            metadata["std"] = float(df["label_value"].std())

        return cls(
            spec=spec,
            series=series_dict,
            metadata=metadata,
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Convert stored series back to DataFrame."""
        return pd.DataFrame(self.series)


# ─────────────────────────────────────────────────────────────────
# LabelSetResult
# ─────────────────────────────────────────────────────────────────


class LabelSetResult(BaseModel):
    """
    Result of computing multiple labels.

    Attributes
    ----------
    labels : dict[str, LabelResult]
        Map from label_name to LabelResult.
    combined_df : dict
        Combined DataFrame with all labels (JSON-serializable).
    """

    labels: dict[str, LabelResult] = Field(default_factory=dict)
    combined_df: dict[str, Any] = Field(default_factory=dict)

    def add(self, result: LabelResult) -> None:
        """Add a LabelResult."""
        self.labels[result.spec.label_name] = result

    def to_combined_dataframe(self) -> pd.DataFrame:
        """
        Merge all label series into a single DataFrame.

        Returns DataFrame with columns: symbol, timestamp, label_1, label_2, ...
        """
        if not self.labels:
            return pd.DataFrame()

        dfs = []
        for name, result in self.labels.items():
            df = result.to_dataframe().rename(columns={"label_value": name})
            dfs.append(df)

        # Merge on symbol + timestamp
        from functools import reduce
        merged = reduce(
            lambda left, right: pd.merge(
                left, right, on=["symbol", "timestamp"], how="outer"
            ),
            dfs,
        )
        return merged

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
