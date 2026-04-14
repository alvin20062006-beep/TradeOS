"""
波动率指标模块
=============

包含:
- ATR (14)
- Bollinger Bands (20, 2)
"""

from __future__ import annotations

import numpy as np
from typing import Optional


def atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Average True Range.
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        period: ATR 周期 (默认 14)
        
    Returns:
        ATR 值序列
    """
    n = len(close)
    if n < period + 1:
        return np.full(n, np.nan)
    
    # True Range
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    
    # ATR (smoothed TR)
    atr_val = np.full(n, np.nan)
    atr_val[period - 1] = np.mean(tr[:period])
    
    for i in range(period, n):
        atr_val[i] = (atr_val[i - 1] * (period - 1) + tr[i]) / period
    
    return atr_val


def bollinger_bands(
    prices: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> dict[str, np.ndarray]:
    """
    Bollinger Bands.
    
    Args:
        prices: 收盘价序列
        period: 周期 (默认 20)
        std_dev: 标准差倍数 (默认 2)
        
    Returns:
        {"upper": 上轨, "middle": 中轨, "lower": 下轨, "bandwidth": 带宽}
    """
    n = len(prices)
    
    # Middle band = SMA
    middle = np.full(n, np.nan)
    for i in range(period - 1, n):
        middle[i] = np.mean(prices[i - period + 1 : i + 1])
    
    # Standard deviation
    std = np.full(n, np.nan)
    for i in range(period - 1, n):
        std[i] = np.std(prices[i - period + 1 : i + 1], ddof=1)
    
    # Upper / Lower
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    
    # Bandwidth (%B)
    bandwidth = np.full(n, np.nan)
    valid = (upper - lower) > 0
    bandwidth[valid] = (prices[valid] - lower[valid]) / (upper[valid] - lower[valid])
    
    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "bandwidth": bandwidth,
    }


def volatility_state(
    atr_val: float,
    atr_ma: float,
    bb_width: float,
) -> str:
    """
    判断波动率状态.
    
    Args:
        atr_val: 当前 ATR 值
        atr_ma: ATR 的移动平均 (用于判断相对高低)
        bb_width: Bollinger 带宽
        
    Returns:
        "expanding" / "contracting" / "neutral"
    """
    if np.isnan(atr_val) or np.isnan(atr_ma) or np.isnan(bb_width):
        return "neutral"
    
    # ATR 高于均值 + 带宽扩张 → 波动率扩张
    if atr_val > atr_ma * 1.2 and bb_width > 0.15:
        return "expanding"
    # ATR 低于均值 + 带宽收窄 → 波动率收缩
    if atr_val < atr_ma * 0.8 and bb_width < 0.05:
        return "contracting"
    
    return "neutral"
