"""
Risk Label Builder
==================
Build risk-based labels for risk management tasks.

Labels:
    - max_drawdown: Maximum drawdown over horizon
    - volatility_percentile: Volatility percentile rank
    - var_breach: Whether VaR was exceeded
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .schema import LabelSpec, LabelResult


# ─────────────────────────────────────────────────────────────────
# Max Drawdown Label Builder
# ─────────────────────────────────────────────────────────────────


class MaxDrawdownLabelBuilder:
    """
    Build max drawdown labels.

    Parameters
    ----------
    horizon : int
        Number of periods to compute drawdown over.
    """

    def __init__(self, horizon: int = 20):
        self.horizon = horizon

    def build_spec(self) -> LabelSpec:
        return LabelSpec(
            label_name=f"max_drawdown_{self.horizon}d",
            label_type="regression",
            horizon=self.horizon,
            horizon_unit="D",
            description=f"Maximum drawdown over {self.horizon} days",
        )

    def compute(
        self,
        data: pd.DataFrame,
        close_col: str = "close",
    ) -> LabelResult:
        """
        Compute max drawdown labels.

        Parameters
        ----------
        data : pd.DataFrame
            Columns: symbol, timestamp, close
        close_col : str

        Returns
        -------
        LabelResult
            label_value: max drawdown (negative value, e.g., -0.15 for 15% drawdown)
        """
        spec = self.build_spec()

        df = data.copy()
        df = df.sort_values(["symbol", "timestamp"])

        def calc_max_dd(prices: pd.Series) -> float:
            """Calculate max drawdown for a price series."""
            rolling_max = prices.expanding().max()
            drawdown = (prices - rolling_max) / rolling_max
            return drawdown.min()

        # Compute rolling max drawdown
        def rolling_dd(group: pd.DataFrame) -> pd.DataFrame:
            group = group.sort_values("timestamp")
            prices = group[close_col]

            # Rolling max drawdown
            max_dd_values = []
            for i in range(len(prices)):
                if i < self.horizon:
                    max_dd_values.append(np.nan)
                else:
                    window = prices.iloc[i - self.horizon + 1 : i + 1]
                    max_dd_values.append(calc_max_dd(window))

            return pd.DataFrame(
                {
                    "symbol": group["symbol"],
                    "timestamp": group["timestamp"],
                    "label_value": max_dd_values,
                }
            )

        result_df = df.groupby("symbol", group_keys=False).apply(rolling_dd)
        result_df = result_df.dropna(subset=["label_value"])
        return LabelResult.from_dataframe(spec, result_df)


# ─────────────────────────────────────────────────────────────────
# Volatility Percentile Label Builder
# ─────────────────────────────────────────────────────────────────


class VolatilityPercentileLabelBuilder:
    """
    Build volatility percentile labels.

    label_value: percentile rank of current volatility (0~1)
    """

    def __init__(self, vol_period: int = 20, lookback: int = 252):
        self.vol_period = vol_period
        self.lookback = lookback

    def build_spec(self) -> LabelSpec:
        return LabelSpec(
            label_name="volatility_percentile",
            label_type="regression",
            horizon=0,  # Current state, not forward
            horizon_unit="D",
            description="Volatility percentile rank (0~1)",
            parameters={"vol_period": self.vol_period, "lookback": self.lookback},
        )

    def compute(
        self,
        data: pd.DataFrame,
        close_col: str = "close",
    ) -> LabelResult:
        spec = self.build_spec()

        df = data.copy()
        df = df.sort_values(["symbol", "timestamp"])

        def calc_vol_percentile(group: pd.DataFrame) -> pd.DataFrame:
            group = group.sort_values("timestamp")
            returns = group[close_col].pct_change()
            vol = returns.rolling(self.vol_period).std() * np.sqrt(252)

            # Percentile rank within lookback
            vol_percentile = vol.rolling(self.lookback).apply(
                lambda x: (x.iloc[-1] > x.iloc[:-1]).mean() if len(x) > 1 else 0.5
            )

            return pd.DataFrame(
                {
                    "symbol": group["symbol"],
                    "timestamp": group["timestamp"],
                    "label_value": vol_percentile,
                }
            )

        result_df = df.groupby("symbol", group_keys=False).apply(calc_vol_percentile)
        result_df = result_df.dropna(subset=["label_value"])
        return LabelResult.from_dataframe(spec, result_df)


# ─────────────────────────────────────────────────────────────────
# VaR Breach Label Builder
# ─────────────────────────────────────────────────────────────────


class VaRBreachLabelBuilder:
    """
    Build VaR breach labels.

    label_value: 1 if return < -VaR, else 0

    Parameters
    ----------
    var_level : float
        VaR confidence level (e.g., 0.05 for 95% VaR).
    var_period : int
        Period for VaR estimation.
    """

    def __init__(self, var_level: float = 0.05, var_period: int = 20):
        self.var_level = var_level
        self.var_period = var_period

    def build_spec(self) -> LabelSpec:
        return LabelSpec(
            label_name=f"var_breach_{int((1-self.var_level)*100)}pct",
            label_type="classification",
            horizon=1,
            horizon_unit="D",
            description=f"VaR breach indicator at {int((1-self.var_level)*100)}% confidence",
            parameters={"var_level": self.var_level, "var_period": self.var_period},
        )

    def compute(
        self,
        data: pd.DataFrame,
        close_col: str = "close",
    ) -> LabelResult:
        spec = self.build_spec()

        df = data.copy()
        df = df.sort_values(["symbol", "timestamp"])

        def calc_var_breach(group: pd.DataFrame) -> pd.DataFrame:
            group = group.sort_values("timestamp")
            returns = group[close_col].pct_change()

            # Historical VaR
            var = returns.rolling(self.var_period).quantile(self.var_level)

            # Forward return
            forward_ret = returns.shift(-1)

            # Breach indicator
            breach = (forward_ret < var).astype(float)

            return pd.DataFrame(
                {
                    "symbol": group["symbol"],
                    "timestamp": group["timestamp"],
                    "label_value": breach,
                }
            )

        result_df = df.groupby("symbol", group_keys=False).apply(calc_var_breach)
        result_df = result_df.dropna(subset=["label_value"])
        return LabelResult.from_dataframe(spec, result_df)


# ─────────────────────────────────────────────────────────────────
# Multi Risk Labels
# ─────────────────────────────────────────────────────────────────


def build_risk_labels(
    data: pd.DataFrame,
    include_drawdown: bool = True,
    include_vol_percentile: bool = True,
    include_var_breach: bool = True,
    close_col: str = "close",
) -> dict[str, LabelResult]:
    """
    Build all risk labels.

    Parameters
    ----------
    data : pd.DataFrame
    include_drawdown, include_vol_percentile, include_var_breach : bool
    close_col : str

    Returns
    -------
    dict[str, LabelResult]
    """
    results = {}

    if include_drawdown:
        builder = MaxDrawdownLabelBuilder(horizon=20)
        results[builder.build_spec().label_name] = builder.compute(data, close_col)

    if include_vol_percentile:
        builder = VolatilityPercentileLabelBuilder()
        results[builder.build_spec().label_name] = builder.compute(data, close_col)

    if include_var_breach:
        builder = VaRBreachLabelBuilder()
        results[builder.build_spec().label_name] = builder.compute(data, close_col)

    return results
