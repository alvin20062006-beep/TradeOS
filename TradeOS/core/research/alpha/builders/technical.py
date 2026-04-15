"""
Technical Alpha Builders
======================

L1 raw technical factors from OHLCV bar data.

These are the most stable baseline factors - all computed from
the 5 standard OHLCV fields which are always available.

Each builder:
- Takes a DataFrame with OHLCV columns
- Returns DataFrame with (symbol, timestamp, raw_value)
- Works on data with or without MultiIndex (auto-detects)

Implemented factors (Constraint 3 priority):
    1. RET_1d    - 1-day return
    2. RET_5d    - 5-day return
    3. VOL_5d    - 5-day rolling volatility (annualised)
    4. VOL_20d   - 20-day rolling volatility (annualised)
    5. RSI_14    - 14-day Relative Strength Index
    6. MACD      - MACD line (12ema - 26ema)
    7. BB_WIDTH  - Bollinger Band width
    8. BB_POS    - Bollinger Band position
    9. VOL_RATIO - Volume ratio vs 20d average
    10. OBV_DIR  - On-Balance Volume direction signal

Constraints followed:
- No data fetching (just compute from input DataFrame)
- Input fields: close (required), open/high/low/volume (optional per factor)
- Output: raw_value only (L1), no normalisation
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


# ── Shared helpers ──────────────────────────────────────────────

def _ensure_multiindex(df: pd.DataFrame, symbol_col: str = "symbol", ts_col: str = "timestamp") -> pd.DataFrame:
    """
    Ensure df has a (symbol, timestamp) MultiIndex.

    Handles three input forms:
    1. Already has MultiIndex -> return as-is
    2. Has symbol + timestamp columns -> set_index
    3. Has DatetimeIndex -> assign dummy symbol='UNKNOWN'
    """
    if isinstance(df.index, pd.MultiIndex):
        return df
    if isinstance(df.index, pd.DatetimeIndex):
        if symbol_col in df.columns:
            df = df.set_index(symbol_col, append=True)
        else:
            df = df.assign(**{symbol_col: "UNKNOWN"}).set_index(symbol_col, append=True)
        return df
    if symbol_col in df.columns and ts_col in df.columns:
        return df.set_index([symbol_col, ts_col])
    return df


def _detect_columns(df: pd.DataFrame) -> dict[str, bool]:
    """Detect which OHLCV columns are available."""
    cols = set(df.columns)
    return {
        "has_open": "open" in cols,
        "has_high": "high" in cols,
        "has_low": "low" in cols,
        "has_close": "close" in cols,
        "has_volume": "volume" in cols,
        "has_vwap": "vwap" in cols,
    }


def _require_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    """Raise ValueError if required columns are missing."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{name} requires columns {required}, but got: {list(df.columns)}. "
            f"Hint: check that your DataFrame has the right columns."
        )


# ── Factor builders ─────────────────────────────────────────────

def build_ret_1d(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    """
    L1: 1-day simple return.

    RET_1d[t] = (close[t] - close[t-1]) / close[t-1]

    Input:  DataFrame with price_col (default: close)
    Output: DataFrame (symbol, timestamp, raw_value)
    """
    _require_columns(df, [price_col], "RET_1d")

    result = df.copy()
    result["raw_value"] = result[price_col].pct_change(1)
    result = result[["raw_value"]].dropna()
    result = result.reset_index()
    result.columns = ["symbol", "timestamp", "raw_value"]
    return result[result["raw_value"].notna()]


def build_ret_5d(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    """
    L1: 5-day simple return.

    RET_5d[t] = (close[t] - close[t-5]) / close[t-5]

    Input:  DataFrame with price_col
    Output: DataFrame (symbol, timestamp, raw_value)
    """
    _require_columns(df, [price_col], "RET_5d")

    result = df.copy()
    result["raw_value"] = result[price_col].pct_change(5)
    result = result[["raw_value"]].dropna()
    result = result.reset_index()
    result.columns = ["symbol", "timestamp", "raw_value"]
    return result[result["raw_value"].notna()]


def build_vol_5d(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    """
    L1: 5-day annualised rolling volatility.

    VOL_5d[t] = std(RET_1d[t-4:t]) * sqrt(252)

    Input:  DataFrame with price_col
    Output: DataFrame (symbol, timestamp, raw_value)
    """
    _require_columns(df, [price_col], "VOL_5d")

    ret = df[price_col].pct_change()
    vol = ret.rolling(window=5, min_periods=5).std() * (252 ** 0.5)
    vol.name = "raw_value"
    vol = vol.dropna().reset_index()
    vol.columns = ["symbol", "timestamp", "raw_value"]
    return vol[vol["raw_value"].notna()]


def build_vol_20d(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    """
    L1: 20-day annualised rolling volatility.

    VOL_20d[t] = std(RET_1d[t-19:t]) * sqrt(252)
    """
    _require_columns(df, [price_col], "VOL_20d")

    ret = df[price_col].pct_change()
    vol = ret.rolling(window=20, min_periods=20).std() * (252 ** 0.5)
    vol.name = "raw_value"
    vol = vol.dropna().reset_index()
    vol.columns = ["symbol", "timestamp", "raw_value"]
    return vol[vol["raw_value"].notna()]


def build_rsi_14(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    """
    L1: 14-day Relative Strength Index.

    RSI_14[t] = 100 - (100 / (1 + RS))
    where RS = avg(gain) / avg(loss) over 14 periods

    Value range: 0-100
    """
    _require_columns(df, [price_col], "RSI_14")

    delta = df[price_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=14, min_periods=14).mean()
    avg_loss = loss.rolling(window=14, min_periods=14).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.dropna()
    rsi.name = "raw_value"
    rsi = rsi.reset_index()
    rsi.columns = ["symbol", "timestamp", "raw_value"]
    return rsi[rsi["raw_value"].notna()]


def build_macd(
    df: pd.DataFrame,
    price_col: str = "close",
    fast: int = 12,
    slow: int = 26,
) -> pd.DataFrame:
    """
    L1: MACD line = fast EMA - slow EMA.

    Default: 12-day EMA - 26-day EMA

    Also used to derive MACD_signal and MACD_histogram
    (available as separate exports from the same df).
    """
    _require_columns(df, [price_col], "MACD")

    ema_fast = df[price_col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[price_col].ewm(span=slow, adjust=False).mean()
    macd = (ema_fast - ema_slow)
    macd.name = "raw_value"
    macd = macd.dropna().reset_index()
    macd.columns = ["symbol", "timestamp", "raw_value"]
    return macd[macd["raw_value"].notna()]


def build_bb_width(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """
    L1: Bollinger Band width = (Upper - Lower) / Middle

    Upper = MA(window) + num_std * std(window)
    Lower = MA(window) - num_std * std(window)
    Middle = MA(window)
    """
    _require_columns(df, [price_col], "BB_WIDTH")

    rolling = df[price_col].rolling(window=window, min_periods=window)
    middle = rolling.mean()
    std = rolling.std()
    upper = middle + num_std * std
    lower = middle - num_std * std

    bb_width = (upper - lower) / middle
    bb_width = bb_width.dropna()
    bb_width.name = "raw_value"
    bb_width = bb_width.reset_index()
    bb_width.columns = ["symbol", "timestamp", "raw_value"]
    return bb_width[bb_width["raw_value"].notna()]


def build_bb_pos(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """
    L1: Bollinger Band position = (close - lower) / (upper - lower)

    Range: 0-1 (below to above middle band)
    """
    _require_columns(df, [price_col], "BB_POS")

    rolling = df[price_col].rolling(window=window, min_periods=window)
    middle = rolling.mean()
    std = rolling.std()
    upper = middle + num_std * std
    lower = middle - num_std * std

    bb_pos = (df[price_col] - lower) / (upper - lower)
    bb_pos = bb_pos.dropna()
    bb_pos.name = "raw_value"
    bb_pos = bb_pos.reset_index()
    bb_pos.columns = ["symbol", "timestamp", "raw_value"]
    return bb_pos[bb_pos["raw_value"].notna()]


def build_vol_ratio(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    L1: Volume ratio = volume / rolling_mean(volume, window)

    VOL_RATIO[t] = volume[t] / mean(volume[t-window+1:t])

    Values > 1 = above-average volume
    Values < 1 = below-average volume
    """
    _require_columns(df, ["volume"], "VOL_RATIO")

    avg_vol = df["volume"].rolling(window=window, min_periods=window).mean()
    ratio = df["volume"] / avg_vol.replace(0, pd.NA)
    ratio = ratio.dropna()
    ratio.name = "raw_value"
    ratio = ratio.reset_index()
    ratio.columns = ["symbol", "timestamp", "raw_value"]
    return ratio[ratio["raw_value"].notna()]


def build_obv_dir(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    L1: On-Balance Volume directional signal.

    OBV_DIR[t] = sign of sum(OBV_change[t-window+1:t])

    Values: +1 (accumulating), -1 (distributing), 0 (neutral)
    """
    _require_columns(df, ["close", "volume"], "OBV_DIR")

    # OBV: accumulate volume on up days
    obv_change = df["volume"] * df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = obv_change.cumsum()

    # Direction: rolling sum of direction over window
    obv_dir = (
        df["close"].diff()
        .apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        .rolling(window=window, min_periods=window)
        .sum()
    )
    # Normalise to -1 / 0 / +1
    obv_dir = obv_dir.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv_dir = obv_dir.dropna()
    obv_dir.name = "raw_value"
    obv_dir = obv_dir.reset_index()
    obv_dir.columns = ["symbol", "timestamp", "raw_value"]
    return obv_dir[obv_dir["raw_value"].notna()]


# ── All technical factor registry ───────────────────────────────

TECHNICAL_FACTORS: dict[str, callable] = {
    "RET_1d": build_ret_1d,
    "RET_5d": build_ret_5d,
    "VOL_5d": build_vol_5d,
    "VOL_20d": build_vol_20d,
    "RSI_14": build_rsi_14,
    "MACD": build_macd,
    "BB_WIDTH": build_bb_width,
    "BB_POS": build_bb_pos,
    "VOL_RATIO": build_vol_ratio,
    "OBV_DIR": build_obv_dir,
}

TECHNICAL_FACTOR_NAMES: list[str] = list(TECHNICAL_FACTORS.keys())


def build_all_technical(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Compute all available technical factors from a DataFrame.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping from factor_name -> (symbol, timestamp, raw_value) DataFrame
        Only factors whose required columns are present are computed.
    """
    available_cols = set(df.columns)
    results = {}

    for name, builder in TECHNICAL_FACTORS.items():
        try:
            required = []
            if name in ("VOL_RATIO", "OBV_DIR"):
                required = ["volume"]
            elif name == "OBV_DIR":
                required = ["close", "volume"]
            else:
                required = ["close"]

            if required[0] in available_cols:
                results[name] = builder(df)
        except (ValueError, KeyError):
            # Skip factors whose columns are not available
            pass

    return results
