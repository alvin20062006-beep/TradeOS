"""
Labels: Schema and Builder Interfaces
====================================
Defines:
    - LabelSetVersion schema (from models.py re-export + here)
    - ILabelBuilder abstract interface
    - ForwardReturnLabel builder
    - DirectionLabel builder
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field

from ..models import LabelSetVersion


# ─────────────────────────────────────────────────────────────────
# Label Builder Interface
# ─────────────────────────────────────────────────────────────────


class ILabelBuilder(ABC):
    """
    Abstract interface for label builders.

    All label builders must implement:
        build()     -> LabelSetVersion (definition + metadata)
        compute()   -> pd.DataFrame[symbol, timestamp, label_value]
    """

    @abstractmethod
    def build(self) -> LabelSetVersion:
        ...

    @abstractmethod
    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute label values.

        Parameters
        ----------
        data : pd.DataFrame
            Must have columns: symbol, timestamp, close (at minimum)

        Returns
        -------
        pd.DataFrame
            Columns: symbol, timestamp, label_value
            index: arbitrary (labels are keyed by symbol+timestamp)
        """
        ...


# ─────────────────────────────────────────────────────────────────
# Forward Return Label Builder
# ─────────────────────────────────────────────────────────────────


class ForwardReturnLabel(ILabelBuilder):
    """
    Build forward return labels for regression tasks.

    label = (price_{t+h} - price_t) / price_t

    Parameters
    ----------
    horizon : int
        Number of periods ahead to compute return.
    horizon_unit : str
        "D", "H", or "min".
    label_type : str
        "regression" (raw return) or "classification" (up/down).
    """

    def __init__(
        self,
        horizon: int = 1,
        horizon_unit: Literal["D", "H", "min"] = "D",
        label_type: Literal["regression", "classification"] = "regression",
        label_name: str = "label",
    ):
        self.horizon = horizon
        self.horizon_unit = horizon_unit
        self.label_type = label_type
        self.label_name = label_name
        self._spec: Optional[LabelSetVersion] = None

    def build(self) -> LabelSetVersion:
        if self._spec is None:
            self._spec = LabelSetVersion(
                label_set_id=str(uuid.uuid4()),
                name=f"forward_return_h{self.horizon}_{self.label_type}",
                label_definitions=[self.label_name],
                horizon=self.horizon,
                horizon_unit=self.horizon_unit,
                label_type=self.label_type,
                version="1.0.0",
                description=(
                    f"Forward return label: horizon={self.horizon}{self.horizon_unit}, "
                    f"type={self.label_type}"
                ),
            )
        return self._spec

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Parameters
        ----------
        data : pd.DataFrame
            Columns: symbol, timestamp, close
            Or index is DatetimeIndex and symbol is in columns.

        Returns
        -------
        pd.DataFrame
            Columns: symbol, timestamp, label_value
        """
        df = data.copy()

        # Normalize: ensure close exists and sort
        if "close" not in df.columns:
            raise ValueError("data must contain 'close' column")
        df = df.sort_values(["symbol", "timestamp"] if "symbol" in df.columns else ["timestamp"])

        # Compute forward return
        h = self.horizon
        df["label_value"] = df.groupby("symbol", group_keys=False)["close"].apply(
            lambda x: x.shift(-h) / x - 1
        )

        if self.label_type == "classification":
            df["label_value"] = (df["label_value"] > 0).astype(float)

        return df[["symbol", "timestamp", "label_value"]].dropna(subset=["label_value"])


# ─────────────────────────────────────────────────────────────────
# Direction Label Builder
# ─────────────────────────────────────────────────────────────────


class DirectionLabel(ILabelBuilder):
    """
    Build binary direction labels (up=1, down=0, neutral=0.5).

    Parameters
    ----------
    horizon : int
        Number of periods ahead.
    threshold : float
        Minimum return magnitude to be considered "up" or "down".
        Returns with magnitude <= threshold are labelled as "neutral" (0.5).
    """

    def __init__(
        self,
        horizon: int = 1,
        threshold: float = 0.0,
        label_name: str = "direction",
    ):
        self.horizon = horizon
        self.threshold = threshold
        self.label_name = label_name
        self._spec: Optional[LabelSetVersion] = None

    def build(self) -> LabelSetVersion:
        if self._spec is None:
            self._spec = LabelSetVersion(
                label_set_id=str(uuid.uuid4()),
                name=f"direction_h{self.horizon}_thr{self.threshold}",
                label_definitions=[self.label_name],
                horizon=self.horizon,
                horizon_unit="D",
                label_type="classification",
                version="1.0.0",
                description=(
                    f"Binary direction label: horizon={self.horizon}, "
                    f"threshold={self.threshold}"
                ),
            )
        return self._spec

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Returns
        -------
        pd.DataFrame
            Columns: symbol, timestamp, label_value
            label_value: 1.0 (up), 0.0 (down), 0.5 (neutral)
        """
        df = data.copy()
        if "close" not in df.columns:
            raise ValueError("data must contain 'close' column")
        df = df.sort_values(["symbol", "timestamp"] if "symbol" in df.columns else ["timestamp"])

        h = self.horizon
        df["ret"] = df.groupby("symbol", group_keys=False)["close"].apply(
            lambda x: x.shift(-h) / x - 1
        )

        # Direction mapping
        def classify(r: float) -> float:
            if r > self.threshold:
                return 1.0
            elif r < -self.threshold:
                return 0.0
            else:
                return 0.5

        df["label_value"] = df["ret"].apply(classify)
        return df[["symbol", "timestamp", "label_value"]].dropna(subset=["label_value"])
