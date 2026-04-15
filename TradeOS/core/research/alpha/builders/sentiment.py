"""
Sentiment Alpha Builders
=====================

L1 raw sentiment factors from volume/price data.

Simplified baseline: VOL_SURPRISE
--------------------------------
This is the most stable and universally available sentiment proxy.

VOL_SURPRISE = (volume[t] - rolling_mean(volume, 20d)) / rolling_std(volume, 20d)

Interpretation:
    > +2  : unusual volume (potential news/event catalyst)
    0     : normal volume
    < -2  : abnormally low volume

This does NOT require external news feeds, social media APIs,
or sentiment databases. It derives a sentiment-adjacent signal
from volume anomalies alone.

Production notes:
- VOL_SURPRISE is a proxy signal, not direct sentiment
- Production sentiment should integrate news/social/analyst feeds
  once those providers are connected to the data layer
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def _require_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{name} requires columns {required}, but got: {list(df.columns)}. "
            f"Available: {list(df.columns)}"
        )


def build_vol_surprise(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    L1: Volume surprise z-score.

    VOL_SURPRISE[t] = (volume[t] - mean(volume[t-20:t])) / std(volume[t-20:t])

    Value interpretation:
        > +2.0 : unusual buying/selling pressure (news catalyst)
        0       : normal volume
        < -2.0  : abnormally quiet

    Requires: volume column

    Parameters
    ----------
    df : pd.DataFrame with MultiIndex (symbol, timestamp) or DatetimeIndex
    window : int, default 20
        Lookback window for rolling stats (trading days)

    Returns
    -------
    pd.DataFrame: symbol, timestamp, raw_value
    """
    _require_columns(df, ["volume"], "VOL_SURPRISE")

    vol = df["volume"]

    # Rolling stats
    rolling_mean = vol.rolling(window=window, min_periods=window).mean()
    rolling_std = vol.rolling(window=window, min_periods=window).std()

    # Z-score of volume
    surprise = (vol - rolling_mean) / rolling_std.replace(0, pd.NA)
    surprise = surprise.dropna()
    surprise.name = "raw_value"
    surprise = surprise.reset_index()
    surprise.columns = ["symbol", "timestamp", "raw_value"]

    return surprise[surprise["raw_value"].notna()]


# ── Sentiment factor registry ─────────────────────────────────────

SENTIMENT_FACTORS: dict[str, callable] = {
    "VOL_SURPRISE": build_vol_surprise,
}

SENTIMENT_FACTOR_NAMES: list[str] = list(SENTIMENT_FACTORS.keys())


def build_all_sentiment(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Compute all available sentiment factors.

    Returns
    -------
    dict[str, pd.DataFrame]
        Only factors whose required columns are present.
    """
    available_cols = set(df.columns)
    results = {}

    for name, builder in SENTIMENT_FACTORS.items():
        try:
            required = ["volume"]
            if required[0] in available_cols:
                results[name] = builder(df)
        except (ValueError, KeyError):
            pass

    return results
