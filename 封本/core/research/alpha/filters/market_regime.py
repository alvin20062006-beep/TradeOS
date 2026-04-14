"""
Market Regime Filter
====================
Detect market regime: trend up/down, range, crisis, recovery.

Uses price and volatility signals to classify market state.
Returns MarketRegimeResult with regime and confidence.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .schema import MarketRegime, MarketRegimeResult


# ─────────────────────────────────────────────────────────────────
# Market Regime Detector
# ─────────────────────────────────────────────────────────────────


def detect_market_regime(
    data: pd.DataFrame,
    lookback: int = 60,
    trend_threshold: float = 0.02,
    vol_percentile_high: float = 0.90,
    vol_percentile_low: float = 0.10,
    close_col: str = "close",
) -> MarketRegimeResult:
    """
    Detect current market regime.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: timestamp, close (single index/market level)
    lookback : int
        Lookback period for calculations.
    trend_threshold : float
        Minimum return over lookback to be considered a trend.
    vol_percentile_high : float
        Volatility percentile threshold for crisis detection.
    vol_percentile_low : float
        Volatility percentile threshold for recovery detection.
    close_col : str

    Returns
    -------
    MarketRegimeResult
    """
    if close_col not in data.columns:
        return MarketRegimeResult(
            regime=MarketRegime.UNKNOWN,
            confidence=0.0,
            indicators={"error": f"Missing column: {close_col}"},
        )

    df = data.sort_values("timestamp")
    if len(df) < lookback:
        return MarketRegimeResult(
            regime=MarketRegime.UNKNOWN,
            confidence=0.0,
            indicators={"error": f"Insufficient data: {len(df)} < {lookback}"},
        )

    # Compute indicators
    close = df[close_col]

    # 1. Trend: return over lookback
    trend_return = close.iloc[-1] / close.iloc[-lookback] - 1

    # 2. Volatility: rolling 20d std, annualized
    returns = close.pct_change()
    vol_series = returns.rolling(20).std() * np.sqrt(252)
    current_vol = vol_series.iloc[-1]
    vol_percentile = (vol_series < current_vol).mean()

    # 3. Recent drawdown
    rolling_max = close.rolling(lookback).max()
    drawdown = (close - rolling_max) / rolling_max
    current_dd = drawdown.iloc[-1]

    # 4. Momentum: 20d return
    momentum_20d = close.iloc[-1] / close.iloc[-20] - 1

    indicators = {
        "trend_return": float(trend_return),
        "current_vol": float(current_vol),
        "vol_percentile": float(vol_percentile),
        "current_drawdown": float(current_dd),
        "momentum_20d": float(momentum_20d),
    }

    # Classification logic
    # Crisis: high volatility percentile + significant drawdown
    if vol_percentile >= vol_percentile_high and current_dd < -0.10:
        return MarketRegimeResult(
            regime=MarketRegime.CRISIS,
            confidence=min(1.0, vol_percentile + abs(current_dd)),
            indicators=indicators,
            timestamp=str(df["timestamp"].iloc[-1]),
        )

    # Recovery: low volatility percentile after drawdown
    if vol_percentile <= vol_percentile_low and current_dd < -0.05 and momentum_20d > 0:
        return MarketRegimeResult(
            regime=MarketRegime.RECOVERY,
            confidence=min(1.0, 1 - vol_percentile + momentum_20d),
            indicators=indicators,
            timestamp=str(df["timestamp"].iloc[-1]),
        )

    # Trend Up: positive trend return above threshold
    if trend_return >= trend_threshold:
        confidence = min(1.0, trend_return / (2 * trend_threshold))
        return MarketRegimeResult(
            regime=MarketRegime.TREND_UP,
            confidence=confidence,
            indicators=indicators,
            timestamp=str(df["timestamp"].iloc[-1]),
        )

    # Trend Down: negative trend return below threshold
    if trend_return <= -trend_threshold:
        confidence = min(1.0, abs(trend_return) / (2 * trend_threshold))
        return MarketRegimeResult(
            regime=MarketRegime.TREND_DOWN,
            confidence=confidence,
            indicators=indicators,
            timestamp=str(df["timestamp"].iloc[-1]),
        )

    # Default: Range
    return MarketRegimeResult(
        regime=MarketRegime.RANGE,
        confidence=0.5,  # Moderate confidence for range
        indicators=indicators,
        timestamp=str(df["timestamp"].iloc[-1]),
    )


# ─────────────────────────────────────────────────────────────────
# Regime History
# ─────────────────────────────────────────────────────────────────


def detect_regime_history(
    data: pd.DataFrame,
    lookback: int = 60,
    step: int = 20,
    **kwargs,
) -> pd.DataFrame:
    """
    Detect regime at multiple points in time.

    Parameters
    ----------
    data : pd.DataFrame
        Columns: timestamp, close
    lookback : int
        Lookback for each detection.
    step : int
        Step between detections.
    **kwargs
        Passed to detect_market_regime().

    Returns
    -------
    pd.DataFrame
        Columns: timestamp, regime, confidence, indicators
    """
    results = []
    df = data.sort_values("timestamp")

    for i in range(lookback, len(df), step):
        subset = df.iloc[:i]
        result = detect_market_regime(subset, lookback=lookback, **kwargs)
        results.append(
            {
                "timestamp": df["timestamp"].iloc[i - 1],
                "regime": result.regime,
                "confidence": result.confidence,
                "indicators": result.indicators,
            }
        )

    return pd.DataFrame(results)


# ─────────────────────────────────────────────────────────────────
# Regime Filter (for use in filter pipeline)
# ─────────────────────────────────────────────────────────────────


def filter_by_regime(
    data: pd.DataFrame,
    allowed_regimes: set[MarketRegime],
    **kwargs,
) -> tuple[bool, MarketRegimeResult]:
    """
    Check if current regime is in allowed set.

    Parameters
    ----------
    data : pd.DataFrame
    allowed_regimes : set[MarketRegime]
        Regimes that allow trading.
    **kwargs
        Passed to detect_market_regime().

    Returns
    -------
    tuple[bool, MarketRegimeResult]
        (is_allowed, regime_result)
    """
    result = detect_market_regime(data, **kwargs)
    is_allowed = result.regime in allowed_regimes
    return is_allowed, result
