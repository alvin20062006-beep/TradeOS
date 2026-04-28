"""
Macro Alpha Builders
====================

L1 raw macro factors.

Baseline placeholder implementation that derives macro-like signals
from the available OHLCV bar data. Does NOT fetch external macro data.

Implemented factors:
    RATE_DELTA    - Short-term return as proxy for rate-of-change
    VOL_TREND     - Volume trend vs price trend divergence
    YIELD_SPREAD  - High-Low spread as proxy for volatility regime

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
# RATE_DELTA: 5-day return as rate-of-change proxy
# ─────────────────────────────────────────────────────────────────


class RateDeltaBuilder(AlphaFactor):
    """
    Rate of change: 5-day return.

    proxy_description: Short-term momentum signal derived from close prices.
    input_fields: ["close"]
    layer: L1
    """

    input_fields = ["close"]
    factor_group = "macro"

    def __init__(self, period: int = 5):
        super().__init__(
            factor_name="RATE_DELTA",
            factor_group="macro",
            source_module="alpha.builders.macro",
            formula_description=f"(close[t] - close[t-{period}]) / close[t-{period}]",
            parameters={"period": period},
        )
        self.period = period

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        df = _ensure_multiindex(data)
        if "close" not in df.columns:
            raise ValueError("RATE_DELTA requires 'close' column")

        result = (
            df.sort_values(["symbol", "timestamp"])
            .groupby("symbol", group_keys=False)
            .apply(
                lambda g: pd.DataFrame(
                    {
                        "symbol": g["symbol"].iloc[0] if "symbol" in g.columns else "UNKNOWN",
                        "timestamp": g["timestamp"],
                        "raw_value": g["close"].pct_change(self.period),
                    }
                )
            )
        )
        return result.dropna(subset=["raw_value"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# VOL_TREND: Volume trend vs price trend divergence
# ─────────────────────────────────────────────────────────────────


class VolTrendBuilder(AlphaFactor):
    """
    Volume trend vs price trend divergence signal.

    proxy_description: (volume_ma - price_ma) / price_ma
    Measures whether volume is expanding faster than price (accumulation/distribution proxy).
    input_fields: ["close", "volume"]
    layer: L1
    """

    input_fields = ["close", "volume"]
    factor_group = "macro"

    def __init__(self, ma_period: int = 20):
        super().__init__(
            factor_name="VOL_TREND",
            factor_group="macro",
            source_module="alpha.builders.macro",
            formula_description="(volume_ma / price_ma - 1)",
            parameters={"ma_period": ma_period},
        )
        self.ma_period = ma_period

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        df = _ensure_multiindex(data)
        missing = set(self.input_fields) - set(df.columns)
        if missing:
            raise ValueError(f"VOL_TREND requires {self.input_fields}, missing: {missing}")

        def calc(g: pd.DataFrame) -> pd.DataFrame:
            g = g.sort_values("timestamp")
            symbol = g["symbol"].iloc[0] if "symbol" in g.columns else "UNKNOWN"
            vol_ma = g["volume"].rolling(self.ma_period).mean()
            price_ma = g["close"].rolling(self.ma_period).mean()
            return pd.DataFrame(
                {
                    "symbol": symbol,
                    "timestamp": g["timestamp"],
                    "raw_value": (vol_ma / price_ma - 1),
                }
            )

        result = (
            df.groupby("symbol", group_keys=False)
            .apply(calc)
        )
        return result.dropna(subset=["raw_value"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# YIELD_SPREAD: High-Low spread as volatility-regime proxy
# ─────────────────────────────────────────────────────────────────


class YieldSpreadBuilder(AlphaFactor):
    """
    (High - Low) / Close as volatility-regime proxy.

    proxy_description: HL_spread = (high - low) / close
    Larger spread = higher volatility regime.
    input_fields: ["high", "low", "close"]
    layer: L1
    """

    input_fields = ["high", "low", "close"]
    factor_group = "macro"

    def __init__(self, smooth_period: int = 5):
        super().__init__(
            factor_name="YIELD_SPREAD",
            factor_group="macro",
            source_module="alpha.builders.macro",
            formula_description="(high - low) / close, smoothed",
            parameters={"smooth_period": smooth_period},
        )
        self.smooth_period = smooth_period

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        df = _ensure_multiindex(data)
        missing = set(self.input_fields) - set(df.columns)
        if missing:
            raise ValueError(f"YIELD_SPREAD requires {self.input_fields}, missing: {missing}")

        def calc(g: pd.DataFrame) -> pd.DataFrame:
            g = g.sort_values("timestamp")
            symbol = g["symbol"].iloc[0] if "symbol" in g.columns else "UNKNOWN"
            hl_spread = (g["high"] - g["low"]) / g["close"]
            return pd.DataFrame(
                {
                    "symbol": symbol,
                    "timestamp": g["timestamp"],
                    "raw_value": hl_spread.rolling(self.smooth_period).mean(),
                }
            )

        result = (
            df.groupby("symbol", group_keys=False)
            .apply(calc)
        )
        return result.dropna(subset=["raw_value"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# Registry helpers
# ─────────────────────────────────────────────────────────────────


def all_macro_builders() -> list[type[AlphaFactor]]:
    """Return all macro factor builder classes."""
    return [RateDeltaBuilder, VolTrendBuilder, YieldSpreadBuilder]


def build_all_macro(data: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all macro factors and stack into a single DataFrame.

    Returns DataFrame with columns: symbol, timestamp, factor_name, raw_value
    """
    frames = []
    for cls in all_macro_builders():
        builder = cls()
        frames.append(builder.compute(data).assign(factor_name=builder.factor_name))
    if not frames:
        return pd.DataFrame(columns=["symbol", "timestamp", "factor_name", "raw_value"])
    return pd.concat(frames, ignore_index=True)
