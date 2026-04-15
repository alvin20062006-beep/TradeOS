"""
支撑阻力位检测模块
================

包含:
- 局部极值点检测
- 水平支撑阻力位
- 动态支撑阻力位 (基于 MA)
"""

from __future__ import annotations

import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class Level:
    """支撑/阻力位."""
    price: float
    strength: float  # 0-1, 强度/置信度
    touches: int  # 触碰次数
    level_type: str  # "support" / "resistance"


def find_pivot_points(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    left_bars: int = 5,
    right_bars: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    找到枢轴点 (Pivot Points).
    
    Args:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        left_bars: 左侧K线数 (默认 5)
        right_bars: 右侧K线数 (默认 5)
        
    Returns:
        (pivot_highs_idx, pivot_lows_idx) 枢轴高/低点索引
    """
    n = len(closes)
    pivot_highs = []
    pivot_lows = []
    
    for i in range(left_bars, n - right_bars):
        # 枢轴高点: 左侧 highs 都低于, 右侧 highs 都低于
        left_lower = all(highs[i] > highs[i - j] for j in range(1, left_bars + 1))
        right_lower = all(highs[i] >= highs[i + j] for j in range(1, right_bars + 1))
        
        if left_lower and right_lower:
            pivot_highs.append(i)
        
        # 枢轴低点: 左侧 lows 都高于, 右侧 lows 都高于
        left_higher = all(lows[i] < lows[i - j] for j in range(1, left_bars + 1))
        right_higher = all(lows[i] <= lows[i + j] for j in range(1, right_bars + 1))
        
        if left_higher and right_higher:
            pivot_lows.append(i)
    
    return np.array(pivot_highs), np.array(pivot_lows)


def detect_support_resistance(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    tolerance_pct: float = 0.02,
    min_touches: int = 2,
    lookback: int = 100,
) -> list[Level]:
    """
    检测支撑阻力位.
    
    Args:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        tolerance_pct: 价格聚合容忍度百分比 (默认 2%)
        min_touches: 最少触碰次数 (默认 2)
        lookback: 回看K线数 (默认 100)
        
    Returns:
        支撑阻力位列表
    """
    n = len(closes)
    if n < 20:
        return []
    
    # 找枢轴点
    pivot_highs, pivot_lows = find_pivot_points(highs, lows, closes)
    
    # 合并相近的价格水平
    all_pivots = list(pivot_highs) + list(pivot_lows)
    all_pivots.sort()
    
    if not all_pivots:
        return []
    
    # 收集所有价格水平
    levels_price = []
    for idx in all_pivots:
        if idx in pivot_highs:
            levels_price.append(highs[idx])
        else:
            levels_price.append(lows[idx])
    
    # 聚类相近水平
    levels_price = np.array(levels_price)
    current_price = closes[-1]
    
    # 简单聚类
    clustered_levels = []
    used = set()
    
    for i, price in enumerate(levels_price):
        if i in used:
            continue
        
        cluster = [price]
        used.add(i)
        
        for j in range(i + 1, len(levels_price)):
            if j in used:
                continue
            if abs(levels_price[j] - price) / price < tolerance_pct:
                cluster.append(levels_price[j])
                used.add(j)
        
        avg_price = np.mean(cluster)
        touches = len(cluster)
        
        if touches >= min_touches:
            # 判断是支撑还是阻力
            if avg_price < current_price:
                level_type = "support"
            else:
                level_type = "resistance"
            
            # 计算强度
            strength = min(1.0, touches / 5)  # 最多 5 次触碰为满强度
            
            clustered_levels.append(Level(
                price=avg_price,
                strength=strength,
                touches=touches,
                level_type=level_type,
            ))
    
    # 按价格排序
    clustered_levels.sort(key=lambda l: l.price)
    
    return clustered_levels


def get_nearest_levels(
    levels: list[Level],
    current_price: float,
    max_levels: int = 3,
) -> dict[str, list[Level]]:
    """
    获取最近的支撑阻力位.
    
    Args:
        levels: 所有水平位
        current_price: 当前价格
        max_levels: 最多返回多少个 (默认 3)
        
    Returns:
        {"support": [...], "resistance": [...]}
    """
    supports = [l for l in levels if l.level_type == "support"]
    resistances = [l for l in levels if l.level_type == "resistance"]
    
    # 距离排序
    supports.sort(key=lambda l: current_price - l.price)  # 从近到远
    resistances.sort(key=lambda l: l.price - current_price)
    
    return {
        "support": supports[:max_levels],
        "resistance": resistances[:max_levels],
    }


def dynamic_support_resistance(
    closes: np.ndarray,
    period: int = 20,
) -> dict[str, np.ndarray]:
    """
    动态支撑阻力 (基于移动平均).
    
    Args:
        closes: 收盘价序列
        period: 周期 (默认 20)
        
    Returns:
        {"upper": 动态阻力, "lower": 动态支撑}
    """
    n = len(closes)
    
    # 简单实现: MA ± 固定偏移
    ma = np.full(n, np.nan)
    for i in range(period - 1, n):
        ma[i] = np.mean(closes[i - period + 1 : i + 1])
    
    # ATR 近似
    atr_approx = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = closes[i - period + 1 : i + 1]
        atr_approx[i] = np.std(window)  # 用标准差近似
    
    # 动态上下轨
    upper = ma + 2 * atr_approx
    lower = ma - 2 * atr_approx
    
    return {"upper": upper, "lower": lower}
