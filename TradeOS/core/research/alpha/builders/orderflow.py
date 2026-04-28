"""
Orderflow Alpha Builders
========================

L1 raw orderflow factors.

Baseline placeholder implementation that derives orderflow-like signals
from the available OHLCV bar data. Does NOT access L2 orderbook data.

Implemented factors:
    VWAP_DEV    - Close deviation from VWAP (price vs volume-weighted price)
    VOL_RATIO   - Volume ratio vs 20d average (already in technical.py, re-export)
    VWAP_SLOPE  - VWAP slope over short window (momentum of volume-weighted price)

Each builder takes a DataFrame with OHLCV columns and returns
DataFrame with (symbol, timestamp, raw_value).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from ..base import AlphaFactor


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────


def _ensure_multiindex(
    df: pd.DataFrame,
    symbol_col: str = "symbol",
    ts_col: str = "timestamp",
) -> pd.DataFrame:
    """Ensure df has (symbol, timestamp) MultiIndex or columns."""
    if isinstance(df.index, pd.MultiIndex):
        return df.reset_index().rename(
            columns={df.index.names[0]: symbol_col, df.index.names[1]: ts_col}
        )
    if isinstance(df.index, pd.DatetimeIndex):
        return df.reset_index().rename(columns={df.index.name: ts_col}).assign(
            symbol="UNKNOWN"
        )
    return df


# ─────────────────────────────────────────────────────────────────
# VWAP_DEV: Close deviation from VWAP
# ─────────────────────────────────────────────────────────────────


class VWAPDeviationBuilder(AlphaFactor):
    """
    Close price deviation from VWAP.

    proxy_description: (close - vwap) / vwap
    Positive = price above VWAP (potential selling pressure)
    Negative = price below VWAP (potential buying opportunity)
    input_fields: ["close", "high", "low", "volume"]
    layer: L1
    """

    input_fields = ["close", "high", "low", "volume"]
    factor_group = "orderflow"

    def __init__(self, vwap_period: int = 20):
        super().__init__(
            factor_name="VWAP_DEV",
            factor_group="orderflow",
            source_module="alpha.builders.orderflow",
            formula_description="(close - vwap) / vwap",
            parameters={"vwap_period": vwap_period},
        )
        self.vwap_period = vwap_period

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        df = _ensure_multiindex(data)
        missing = set(self.input_fields) - set(df.columns)
        if missing:
            raise ValueError(f"VWAP_DEV requires {self.input_fields}, missing: {missing}")

        def calc(g: pd.DataFrame) -> pd.DataFrame:
            g = g.sort_values("timestamp")
            symbol = g["symbol"].iloc[0] if "symbol" in g.columns else "UNKNOWN"
            # Typical price = (high + low + close) / 3
            tp = (g["high"] + g["low"] + g["close"]) / 3
            vwap = (tp * g["volume"]).rolling(self.vwap_period).sum() / g["volume"].rolling(
                self.vwap_period
            ).sum()
            return pd.DataFrame(
                {
                    "symbol": symbol,
                    "timestamp": g["timestamp"],
                    "raw_value": (g["close"] - vwap) / vwap,
                }
            )

        result = df.groupby("symbol", group_keys=False).apply(calc)
        return result.dropna(subset=["raw_value"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# VWAP_SLOPE: VWAP momentum over short window
# ─────────────────────────────────────────────────────────────────


class VWAPSlopeBuilder(AlphaFactor):
    """
    VWAP slope (momentum of volume-weighted price).

    proxy_description: (vwap[t] - vwap[t-n]) / vwap[t-n]
    Positive slope = accumulation pressure
    Negative slope = distribution pressure
    input_fields: ["high", "low", "close", "volume"]
    layer: L1
    """

    input_fields = ["high", "low", "close", "volume"]
    factor_group = "orderflow"

    def __init__(self, vwap_period: int = 20, slope_period: int = 5):
        super().__init__(
            factor_name="VWAP_SLOPE",
            factor_group="orderflow",
            source_module="alpha.builders.orderflow",
            formula_description="(vwap[t] - vwap[t-n]) / vwap[t-n]",
            parameters={"vwap_period": vwap_period, "slope_period": slope_period},
        )
        self.vwap_period = vwap_period
        self.slope_period = slope_period

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        df = _ensure_multiindex(data)
        missing = set(self.input_fields) - set(df.columns)
        if missing:
            raise ValueError(f"VWAP_SLOPE requires {self.input_fields}, missing: {missing}")

        def calc(g: pd.DataFrame) -> pd.DataFrame:
            g = g.sort_values("timestamp")
            symbol = g["symbol"].iloc[0] if "symbol" in g.columns else "UNKNOWN"
            tp = (g["high"] + g["low"] + g["close"]) / 3
            vwap = (tp * g["volume"]).rolling(self.vwap_period).sum() / g["volume"].rolling(
                self.vwap_period
            ).sum()
            return pd.DataFrame(
                {
                    "symbol": symbol,
                    "timestamp": g["timestamp"],
                    "raw_value": vwap.pct_change(self.slope_period),
                }
            )

        result = df.groupby("symbol", group_keys=False).apply(calc)
        return result.dropna(subset=["raw_value"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# VOLUME_CONCENTRATION: Volume spike detection
# ─────────────────────────────────────────────────────────────────


class VolumeConcentrationBuilder(AlphaFactor):
    """
    Volume concentration: current volume vs recent average.

    proxy_description: volume / volume_ma - 1
    High values = unusual volume activity (potential breakout/breakdown)
    input_fields: ["volume"]
    layer: L1
    """

    input_fields = ["volume"]
    factor_group = "orderflow"

    def __init__(self, ma_period: int = 20):
        super().__init__(
            factor_name="VOL_CONCENTRATION",
            factor_group="orderflow",
            source_module="alpha.builders.orderflow",
            formula_description="volume / volume_ma - 1",
            parameters={"ma_period": ma_period},
        )
        self.ma_period = ma_period

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        df = _ensure_multiindex(data)
        if "volume" not in df.columns:
            raise ValueError("VOL_CONCENTRATION requires 'volume' column")

        def calc(g: pd.DataFrame) -> pd.DataFrame:
            g = g.sort_values("timestamp")
            symbol = g["symbol"].iloc[0] if "symbol" in g.columns else "UNKNOWN"
            vol_ma = g["volume"].rolling(self.ma_period).mean()
            return pd.DataFrame(
                {
                    "symbol": symbol,
                    "timestamp": g["timestamp"],
                    "raw_value": g["volume"] / vol_ma - 1,
                }
            )

        result = df.groupby("symbol", group_keys=False).apply(calc)
        return result.dropna(subset=["raw_value"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# Registry helpers
# ─────────────────────────────────────────────────────────────────


def all_orderflow_builders() -> list[type[AlphaFactor]]:
    """Return all orderflow factor builder classes."""
    return [VWAPDeviationBuilder, VWAPSlopeBuilder, VolumeConcentrationBuilder]


def build_all_orderflow(data: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all orderflow factors and stack into a single DataFrame.

    Returns DataFrame with columns: symbol, timestamp, factor_name, raw_value
    """
    frames = []
    for cls in all_orderflow_builders():
        builder = cls()
        frames.append(builder.compute(data).assign(factor_name=builder.factor_name))
    if not frames:
        return pd.DataFrame(columns=["symbol", "timestamp", "factor_name", "raw_value"])
    return pd.concat(frames, ignore_index=True)
