"""
趋势指标模块
===========

包含:
- MA (Simple Moving Average)
- EMA (Exponential Moving Average)
- ADX (Average Directional Index)
"""

from __future__ import annotations

import numpy as np
from typing import Optional


def sma(prices: np.ndarray, period: int) -> np.ndarray:
    """
    Simple Moving Average.
    
    Args:
        prices: 价格序列 (close)
        period: 周期
        
    Returns:
        SMA 序列 (前 period-1 个为 nan)
    """
    if len(prices) < period:
        return np.full(len(prices), np.nan)
    
    result = np.full(len(prices), np.nan)
    for i in range(period - 1, len(prices)):
        result[i] = np.mean(prices[i - period + 1 : i + 1])
    return result


def ema(prices: np.ndarray, period: int) -> np.ndarray:
    """
    Exponential Moving Average.
    
    Args:
        prices: 价格序列 (close)
        period: 周期
        
    Returns:
        EMA 序列
    """
    if len(prices) < period:
        return np.full(len(prices), np.nan)
    
    result = np.zeros(len(prices))
    result[: period - 1] = np.nan
    result[period - 1] = np.mean(prices[:period])
    
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(prices)):
        result[i] = (prices[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def adx(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> dict[str, np.ndarray]:
    """
    Average Directional Index.
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: ADX 周期 (默认 14)
        
    Returns:
        {
            "adx": ADX 值序列,
            "plus_di": +DI 序列,
            "minus_di": -DI 序列,
        }
    """
    n = len(high)
    if n < period + 1:
        nan_arr = np.full(n, np.nan)
        return {"adx": nan_arr, "plus_di": nan_arr, "minus_di": nan_arr}
    
    # True Range
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    
    # Directional Movement
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
    
    # Smoothed TR / DM
    atr = np.full(n, np.nan)
    plus_dm_smooth = np.full(n, np.nan)
    minus_dm_smooth = np.full(n, np.nan)
    
    atr[period - 1] = np.sum(tr[:period])
    plus_dm_smooth[period - 1] = np.sum(plus_dm[:period])
    minus_dm_smooth[period - 1] = np.sum(minus_dm[:period])
    
    for i in range(period, n):
        atr[i] = atr[i - 1] - atr[i - 1] / period + tr[i]
        plus_dm_smooth[i] = plus_dm_smooth[i - 1] - plus_dm_smooth[i - 1] / period + plus_dm[i]
        minus_dm_smooth[i] = minus_dm_smooth[i - 1] - minus_dm_smooth[i - 1] / period + minus_dm[i]
    
    # Directional Index
    plus_di = np.where(atr > 0, 100 * plus_dm_smooth / atr, 0)
    minus_di = np.where(atr > 0, 100 * minus_dm_smooth / atr, 0)
    
    # DX
    dx = np.where(
        (plus_di + minus_di) > 0,
        100 * np.abs(plus_di - minus_di) / (plus_di + minus_di),
        0,
    )
    
    # ADX (smoothed DX)
    adx = np.full(n, np.nan)
    adx[2 * period - 2] = np.mean(dx[period - 1 : 2 * period - 1])
    for i in range(2 * period - 1, n):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    
    return {"adx": adx, "plus_di": plus_di, "minus_di": minus_di}


def trend_direction(ma_values: dict[int, np.ndarray], idx: int) -> str:
    """
    根据 MA 系统判断趋势方向.
    
    Args:
        ma_values: {period: ma_array}
        idx: 当前索引
        
    Returns:
        "up" / "down" / "sideways"
    """
    required = [5, 20, 60]
    if not all(p in ma_values for p in required):
        return "sideways"
    
    ma5 = ma_values[5][idx]
    ma20 = ma_values[20][idx]
    ma60 = ma_values[60][idx]
    
    if np.isnan(ma5) or np.isnan(ma20) or np.isnan(ma60):
        return "sideways"
    
    # 多头排列: MA5 > MA20 > MA60
    if ma5 > ma20 > ma60:
        return "up"
    # 空头排列: MA5 < MA20 < MA60
    if ma5 < ma20 < ma60:
        return "down"
    
    return "sideways"
