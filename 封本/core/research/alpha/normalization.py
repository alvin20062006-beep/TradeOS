"""
AlphaNormalizer - Statistical normalization for alpha factors.
L2 layer: winsorize / zscore / rank / neutralize.

See docs/architecture/alpha_factor_architecture.md for full design.
"""

from __future__ import annotations

from typing import Literal, Optional

import numpy as np
import pandas as pd


class AlphaNormalizer:
    """
    Apply L2 normalization to factor values.

    Methods
    -------
    winsorize(df, lower=0.01, upper=0.99)
        Clip values at percentiles.
    zscore(df, cross_sectional=True)
        (x - mean) / std per cross-section or time-series.
    rank(df)
        Cross-sectional percentile rank (0 ~ 1).
    neutralize(df, market_returns)
        Residual after regressing on market/sector returns.
    apply(df, method="zscore")
        Apply the specified method.
    """

    def __init__(
        self,
        default_method: Literal["none", "winsorize", "zscore", "rank"] = "zscore",
        lower: float = 0.01,
        upper: float = 0.99,
    ):
        self.default_method = default_method
        self.lower = lower
        self.upper = upper

    def apply(
        self,
        factor_values: pd.DataFrame,
        method: Optional[Literal["none", "winsorize", "zscore", "rank"]] = None,
    ) -> pd.DataFrame:
        """
        Apply normalization to factor values.

        Parameters
        ----------
        factor_values : pd.DataFrame
            Columns: symbol, timestamp, raw_value
        method : str, optional
            Normalization method. Uses default_method if not provided.

        Returns
        -------
        pd.DataFrame
            Same columns as input, adds `normalized_value`.
        """
        method = method or self.default_method

        if method == "none" or method is None:
            return factor_values

        df = factor_values.copy()

        if method == "winsorize":
            df["normalized_value"] = self.winsorize(df["raw_value"])
        elif method == "zscore":
            df["normalized_value"] = self.zscore(df["raw_value"])
        elif method == "rank":
            df["normalized_value"] = self.rank(df["raw_value"])
        else:
            raise ValueError(f"Unknown normalization method: {method}")

        return df

    @staticmethod
    def winsorize(
        series: pd.Series,
        lower: float = 0.01,
        upper: float = 0.99,
    ) -> pd.Series:
        """Clip values at specified percentiles."""
        lo = series.quantile(lower)
        hi = series.quantile(upper)
        return series.clip(lower=lo, upper=hi)

    @staticmethod
    def zscore(
        series: pd.Series,
        cross_sectional: bool = True,
    ) -> pd.Series:
        """
        Z-score normalization.

        If cross_sectional=True, z-score per timestamp (cross-section).
        Otherwise, z-score over the entire series.
        """
        if cross_sectional:
            # Group by timestamp (if multi-symbol)
            def _zscore(group: pd.Series) -> pd.Series:
                if group.std() == 0 or group.isna().all():
                    return pd.Series(0.0, index=group.index)
                return (group - group.mean()) / group.std()

            return series.groupby(level="timestamp" if isinstance(series.index, pd.MultiIndex) else series.index).transform(_zscore)
        else:
            if series.std() == 0:
                return pd.Series(0.0, index=series.index)
            return (series - series.mean()) / series.std()

    @staticmethod
    def rank(series: pd.Series) -> pd.Series:
        """
        Cross-sectional percentile rank 0 ~ 1.

        Rank within each timestamp group.
        """
        def _rank(group: pd.Series) -> pd.Series:
            return group.rank(pct=True)
        return series.groupby(level="timestamp" if isinstance(series.index, pd.MultiIndex) else series.index).transform(_rank)

    @staticmethod
    def neutralize(
        factor_values: pd.DataFrame,
        market_returns: Optional[pd.Series] = None,
    ) -> pd.Series:
        """
        Neutralize factor by regressing out market/sector exposure.

        Returns residual series.
        """
        # Placeholder: full implementation requires market returns series
        # aligned by timestamp.
        if market_returns is None:
            return factor_values["raw_value"]
        return factor_values["raw_value"]  # TODO: residual after regression
