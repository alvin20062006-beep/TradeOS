"""
Returns Label Builder
=====================
Build return-based labels for regression tasks.

Labels:
    - return_1d: 1-day forward return
    - return_5d: 5-day forward return
    - return_20d: 20-day forward return
    - excess_return: return vs benchmark
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .schema import LabelSpec, LabelResult


# ─────────────────────────────────────────────────────────────────
# Return Label Builder
# ─────────────────────────────────────────────────────────────────


class ReturnLabelBuilder:
    """
    Build forward return labels.

    Parameters
    ----------
    horizon : int
        Number of periods ahead.
    horizon_unit : str
        "D" | "H" | "min".
    """

    def __init__(
        self,
        horizon: int = 1,
        horizon_unit: str = "D",
    ):
        self.horizon = horizon
        self.horizon_unit = horizon_unit

    def build_spec(self) -> LabelSpec:
        """Build the LabelSpec for this label."""
        return LabelSpec(
            label_name=f"return_{self.horizon}{self.horizon_unit.lower()}",
            label_type="regression",
            horizon=self.horizon,
            horizon_unit=self.horizon_unit,
            description=f"Forward return over {self.horizon} {self.horizon_unit}",
        )

    def compute(
        self,
        data: pd.DataFrame,
        close_col: str = "close",
    ) -> LabelResult:
        """
        Compute return labels.

        Parameters
        ----------
        data : pd.DataFrame
            Columns: symbol, timestamp, close
        close_col : str

        Returns
        -------
        LabelResult
        """
        spec = self.build_spec()

        df = data.copy()
        if close_col not in df.columns:
            raise ValueError(f"Missing column: {close_col}")

        # Ensure sorted
        df = df.sort_values(["symbol", "timestamp"])

        # Compute forward return
        df["label_value"] = df.groupby("symbol", group_keys=False)[close_col].apply(
            lambda x: x.shift(-self.horizon) / x - 1
        )

        result_df = df[["symbol", "timestamp", "label_value"]].dropna(subset=["label_value"])
        return LabelResult.from_dataframe(spec, result_df)


# ─────────────────────────────────────────────────────────────────
# Excess Return Label Builder
# ─────────────────────────────────────────────────────────────────


class ExcessReturnLabelBuilder:
    """
    Build excess return labels vs benchmark.

    Parameters
    ----------
    horizon : int
    benchmark_returns : pd.Series
        Benchmark returns indexed by timestamp.
    """

    def __init__(
        self,
        horizon: int = 1,
        benchmark_returns: Optional[pd.Series] = None,
    ):
        self.horizon = horizon
        self.benchmark_returns = benchmark_returns

    def build_spec(self) -> LabelSpec:
        return LabelSpec(
            label_name=f"excess_return_{self.horizon}d",
            label_type="regression",
            horizon=self.horizon,
            horizon_unit="D",
            description=f"Excess return over {self.horizon} days vs benchmark",
        )

    def compute(
        self,
        data: pd.DataFrame,
        close_col: str = "close",
    ) -> LabelResult:
        """
        Compute excess return labels.

        Parameters
        ----------
        data : pd.DataFrame
            Columns: symbol, timestamp, close
        close_col : str

        Returns
        -------
        LabelResult
        """
        spec = self.build_spec()

        df = data.copy()
        df = df.sort_values(["symbol", "timestamp"])

        # Compute stock return
        df["stock_return"] = df.groupby("symbol", group_keys=False)[close_col].apply(
            lambda x: x.shift(-self.horizon) / x - 1
        )

        # Subtract benchmark return
        if self.benchmark_returns is not None:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.merge(
                self.benchmark_returns.rename("bench_return"),
                left_on="timestamp",
                right_index=True,
                how="left",
            )
            df["label_value"] = df["stock_return"] - df["bench_return"].fillna(0)
        else:
            df["label_value"] = df["stock_return"]

        result_df = df[["symbol", "timestamp", "label_value"]].dropna(subset=["label_value"])
        return LabelResult.from_dataframe(spec, result_df)


# ─────────────────────────────────────────────────────────────────
# Multi-Horizon Return Labels
# ─────────────────────────────────────────────────────────────────


def build_return_labels(
    data: pd.DataFrame,
    horizons: list[int] = [1, 5, 20],
    close_col: str = "close",
) -> dict[str, LabelResult]:
    """
    Build return labels for multiple horizons.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: symbol, timestamp, close
    horizons : list[int]
    close_col : str

    Returns
    -------
    dict[str, LabelResult]
        Map from label_name to LabelResult.
    """
    results = {}
    for h in horizons:
        builder = ReturnLabelBuilder(horizon=h)
        results[builder.build_spec().label_name] = builder.compute(data, close_col)
    return results
