"""
Direction Label Builder
======================
Build direction labels for classification tasks.

Labels:
    - direction_1d: up/down/neutral (1/0/0.5)
    - direction_5d: up/down/neutral
    - ternary_direction: 3-class (up/neutral/down)
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .schema import LabelSpec, LabelResult


# ─────────────────────────────────────────────────────────────────
# Direction Label Builder
# ─────────────────────────────────────────────────────────────────


class DirectionLabelBuilder:
    """
    Build binary direction labels.

    Parameters
    ----------
    horizon : int
        Number of periods ahead.
    threshold : float
        Minimum return magnitude to be considered "up" or "down".
        Returns with magnitude <= threshold are labelled "neutral".
    """

    def __init__(
        self,
        horizon: int = 1,
        threshold: float = 0.0,
    ):
        self.horizon = horizon
        self.threshold = threshold

    def build_spec(self) -> LabelSpec:
        """Build the LabelSpec for this label."""
        return LabelSpec(
            label_name=f"direction_{self.horizon}d",
            label_type="classification",
            horizon=self.horizon,
            horizon_unit="D",
            description=f"Direction label over {self.horizon} days, threshold={self.threshold}",
            parameters={"threshold": self.threshold},
        )

    def compute(
        self,
        data: pd.DataFrame,
        close_col: str = "close",
    ) -> LabelResult:
        """
        Compute direction labels.

        Parameters
        ----------
        data : pd.DataFrame
            Columns: symbol, timestamp, close
        close_col : str

        Returns
        -------
        LabelResult
            label_value: 1.0 (up), 0.0 (down), 0.5 (neutral)
        """
        spec = self.build_spec()

        df = data.copy()
        df = df.sort_values(["symbol", "timestamp"])

        # Compute forward return
        df["ret"] = df.groupby("symbol", group_keys=False)[close_col].apply(
            lambda x: x.shift(-self.horizon) / x - 1
        )

        # Direction mapping
        def classify(r: float) -> float:
            if pd.isna(r):
                return float("nan")
            if r > self.threshold:
                return 1.0
            elif r < -self.threshold:
                return 0.0
            else:
                return 0.5

        df["label_value"] = df["ret"].apply(classify)
        result_df = df[["symbol", "timestamp", "label_value"]].dropna(subset=["label_value"])
        return LabelResult.from_dataframe(spec, result_df)


# ─────────────────────────────────────────────────────────────────
# Ternary Direction Label Builder
# ─────────────────────────────────────────────────────────────────


class TernaryDirectionLabelBuilder:
    """
    Build 3-class direction labels.

    label_value: 0 (down), 1 (neutral), 2 (up)
    """

    def __init__(
        self,
        horizon: int = 1,
        threshold: float = 0.01,
    ):
        self.horizon = horizon
        self.threshold = threshold

    def build_spec(self) -> LabelSpec:
        return LabelSpec(
            label_name=f"ternary_direction_{self.horizon}d",
            label_type="ordinal",
            horizon=self.horizon,
            horizon_unit="D",
            description=f"3-class direction: 0=down, 1=neutral, 2=up (threshold={self.threshold})",
            parameters={"threshold": self.threshold},
        )

    def compute(
        self,
        data: pd.DataFrame,
        close_col: str = "close",
    ) -> LabelResult:
        spec = self.build_spec()

        df = data.copy()
        df = df.sort_values(["symbol", "timestamp"])

        df["ret"] = df.groupby("symbol", group_keys=False)[close_col].apply(
            lambda x: x.shift(-self.horizon) / x - 1
        )

        def classify(r: float) -> float:
            if pd.isna(r):
                return float("nan")
            if r > self.threshold:
                return 2.0
            elif r < -self.threshold:
                return 0.0
            else:
                return 1.0

        df["label_value"] = df["ret"].apply(classify)
        result_df = df[["symbol", "timestamp", "label_value"]].dropna(subset=["label_value"])
        return LabelResult.from_dataframe(spec, result_df)


# ─────────────────────────────────────────────────────────────────
# Multi-Threshold Direction Labels
# ─────────────────────────────────────────────────────────────────


def build_direction_labels(
    data: pd.DataFrame,
    horizons: list[int] = [1, 5],
    thresholds: list[float] = [0.0, 0.01],
    close_col: str = "close",
) -> dict[str, LabelResult]:
    """
    Build direction labels for multiple horizons and thresholds.

    Parameters
    ----------
    data : pd.DataFrame
    horizons : list[int]
    thresholds : list[float]
    close_col : str

    Returns
    -------
    dict[str, LabelResult]
    """
    results = {}
    for h in horizons:
        for thr in thresholds:
            builder = DirectionLabelBuilder(horizon=h, threshold=thr)
            results[builder.build_spec().label_name] = builder.compute(data, close_col)
    return results
