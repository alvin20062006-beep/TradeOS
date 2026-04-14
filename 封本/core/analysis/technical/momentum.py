"""
动量指标模块
===========

包含:
- MACD (12/26/9)
- RSI (14)
- KDJ (9/3/3)
- CCI (20)
"""

from __future__ import annotations

import numpy as np
from typing import Optional


def macd(
    prices: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, np.ndarray]:
    """
    MACD 指标.
    
    Args:
        prices: 收盘价序列
        fast: 快线周期 (默认 12)
        slow: 慢线周期 (默认 26)
        signal: 信号线周期 (默认 9)
        
    Returns:
        {"line": MACD线, "signal": 信号线, "histogram": 柱状图}
    """
    n = len(prices)
    
    # EMA fast/slow
    ema_fast = _ema(prices, fast)
    ema_slow = _ema(prices, slow)
    
    # MACD Line
    macd_line = ema_fast - ema_slow
    
    # Signal Line (EMA of MACD)
    signal_line = _ema(macd_line[slow - 1 :], signal)
    signal_full = np.full(n, np.nan)
    signal_full[slow - 1 :] = signal_line
    
    # Histogram
    histogram = macd_line - signal_full
    
    return {"line": macd_line, "signal": signal_full, "histogram": histogram}


def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Relative Strength Index.
    
    Args:
        prices: 收盘价序列
        period: RSI 周期 (默认 14)
        
    Returns:
        RSI 值序列 [0-100]
    """
    n = len(prices)
    if n < period + 1:
        return np.full(n, np.nan)
    
    # Price changes
    deltas = np.diff(prices)
    
    # Gains / Losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # Initial averages
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)
    
    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])
    
    # Smoothed averages (Wilder's method)
    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period
    
    # RSI
    rsi_val = np.full(n, np.nan)
    rs = avg_gain[period:] / np.where(avg_loss[period:] == 0, 1e-10, avg_loss[period:])
    rsi_val[period:] = 100 - 100 / (1 + rs)
    
    return rsi_val


def kdj(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> dict[str, np.ndarray]:
    """
    KDJ 指标.
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        n: RSV 周期 (默认 9)
        m1: K 周期 (默认 3)
        m2: D 周期 (默认 3)
        
    Returns:
        {"k": K 值, "d": D 值, "j": J 值}
    """
    length = len(close)
    if length < n:
        nan_arr = np.full(length, np.nan)
        return {"k": nan_arr, "d": nan_arr, "j": nan_arr}
    
    # RSV (Raw Stochastic Value)
    rsv = np.full(length, np.nan)
    for i in range(n - 1, length):
        low_n = np.min(low[i - n + 1 : i + 1])
        high_n = np.max(high[i - n + 1 : i + 1])
        if high_n != low_n:
            rsv[i] = 100 * (close[i] - low_n) / (high_n - low_n)
        else:
            rsv[i] = 50
    
    # K, D, J
    k = np.full(length, np.nan)
    d = np.full(length, np.nan)
    j = np.full(length, np.nan)
    
    k[n - 1] = 50
    d[n - 1] = 50
    
    for i in range(n, length):
        k[i] = (k[i - 1] * (m1 - 1) + rsv[i]) / m1
        d[i] = (d[i - 1] * (m2 - 1) + k[i]) / m2
        j[i] = 3 * k[i] - 2 * d[i]
    
    return {"k": k, "d": d, "j": j}


def cci(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Commodity Channel Index.
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: CCI 周期 (默认 20)
        
    Returns:
        CCI 值序列
    """
    n = len(close)
    if n < period:
        return np.full(n, np.nan)
    
    # Typical Price
    tp = (high + low + close) / 3
    
    cci_val = np.full(n, np.nan)
    for i in range(period - 1, n):
        tp_window = tp[i - period + 1 : i + 1]
        tp_sma = np.mean(tp_window)
        # Mean Deviation
        md = np.mean(np.abs(tp_window - tp_sma))
        if md > 0:
            cci_val[i] = (tp[i] - tp_sma) / (0.015 * md)
        else:
            cci_val[i] = 0
    
    return cci_val


def momentum_state(rsi_val: float, macd_hist: float) -> str:
    """
    判断动量状态.
    
    Args:
        rsi_val: 当前 RSI 值
        macd_hist: 当前 MACD histogram 值
        
    Returns:
        "strengthening" / "weakening" / "neutral"
    """
    if np.isnan(rsi_val) or np.isnan(macd_hist):
        return "neutral"
    
    # RSI > 60 且 histogram 为正 → 动量加强
    if rsi_val > 60 and macd_hist > 0:
        return "strengthening"
    # RSI < 40 且 histogram 为负 → 动量减弱
    if rsi_val < 40 and macd_hist < 0:
        return "weakening"
    
    return "neutral"


def _ema(prices: np.ndarray, period: int) -> np.ndarray:
    """内部 EMA 计算."""
    n = len(prices)
    result = np.zeros(n)
    result[: period - 1] = np.nan
    result[period - 1] = np.mean(prices[:period])
    
    multiplier = 2.0 / (period + 1)
    for i in range(period, n):
        result[i] = (prices[i] - result[i - 1]) * multiplier + result[i - 1]
    return result
