"""
背驰判断模块 (Divergence)
======================

缠论核心：判断背驰（力度衰竭）。

背驰类型:
- 顶背驰：价格创新高，但上涨力度减弱（MACD柱面积/长度减小）
- 底背驰：价格创新低，但下跌力度减弱

判断方法（简化）:
1. 价格创新高/低
2. 对应位置的 MACD 柱子长度 / 高度是否减弱
3. 背驰 = 价格创新高/低，但 MACD 柱子没有创新高/低
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .strokes import Stroke, StrokeDirection
from .segments import Segment, SegmentDirection


class DivergenceType(str, Enum):
    """背驰类型."""
    BULLISH = "bullish"    # 底背驰（看涨）
    BEARISH = "bearish"    # 顶背驰（看跌）
    NONE = "none"          # 无背驰


@dataclass
class Divergence:
    """背驰结构."""
    divergence_type: DivergenceType
    price_extremum_idx: int      # 价格极值索引
    macd_extremum_idx: int        # MACD极值索引
    price_extremum_value: float   # 价格极值
    macd_extremum_value: float   # MACD极值
    macd_prev_extremum_value: float  # 前一个MACD极值
    price_prev_extremum_value: float  # 前一个价格极值
    severity: float               # 背驰严重程度 0-1
    description: str

    def __repr__(self):
        return (f"Divergence({self.divergence_type.value}, "
                f"price={self.price_extremum_value:.2f}, "
                f"macd={self.macd_extremum_value:.4f}, "
                f"severity={self.severity:.2f})")


def macd_strength(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> np.ndarray:
    """
    计算 MACD 柱子强度（用于背驰判断）。
    
    返回: MACD histogram 序列（正值=多头，负值=空头）
    """
    n = len(closes)

    # EMA helper (uses input length, not n)
    def ema_arr(prices, period):
        m = len(prices)
        if m < period:
            return np.full(m, np.nan)
        result = np.zeros(m)
        result[:period - 1] = np.nan
        result[period - 1] = np.mean(prices[:period])
        mult = 2.0 / (period + 1)
        for i in range(period, m):
            result[i] = (prices[i] - result[i - 1]) * mult + result[i - 1]
        return result

    ema_fast = ema_arr(closes, fast)
    ema_slow = ema_arr(closes, slow)
    macd_line = ema_fast - ema_slow

    sig = ema_arr(macd_line[slow - 1:], signal_period)
    signal_full = np.full(n, np.nan)
    signal_full[slow - 1:] = sig
    
    histogram = macd_line - signal_full
    return histogram


def _find_pole(series: np.ndarray, direction: str) -> tuple[int, float]:
    """
    找到序列的极值点。
    
    Args:
        series: 数据序列
        direction: "max" 或 "min"
        
    Returns:
        (index, value)
    """
    valid = ~np.isnan(series)
    if not np.any(valid):
        return -1, 0.0
    
    if direction == "max":
        idx = np.argmax(np.where(valid, series, -np.inf))
    else:
        idx = np.argmin(np.where(valid, series, np.inf))
    
    return idx, series[idx]


def detect_divergence(
    strokes: list[Stroke],
    segments: list[Segment],
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
) -> list[Divergence]:
    """
    检测背驰信号。
    
    算法（简化版）:
    1. 找到最近的上升/下降笔
    2. 比较相邻同向笔的力度（高度 + MACD 柱子面积）
    3. 价格创新高/低但 MACD 没创新高/低 → 背驰
    
    Args:
        strokes: 笔列表
        segments: 线段列表
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        macd_fast/slow/signal: MACD 参数
        
    Returns:
        背驰列表
    """
    if len(strokes) < 3:
        return []

    divergences: list[Divergence] = []
    macd_hist = macd_strength(highs, lows, closes, macd_fast, macd_slow, macd_signal)

    # 找最近的几笔做背驰检测
    recent_strokes = strokes[-min(6, len(strokes)):]
    start_offset = len(strokes) - len(recent_strokes)

    # 同向笔配对比较
    i = 0
    while i < len(recent_strokes) - 1:
        s1 = recent_strokes[i]
        s2 = recent_strokes[i + 1]

        # 必须是同向笔
        if s1.direction != s2.direction:
            i += 1
            continue

        # 获取两笔对应区间的MACD柱子总和（力度代理）
        macd_area1 = _macd_area(macd_hist, s1.start_idx, s1.end_idx)
        macd_area2 = _macd_area(macd_hist, s2.start_idx, s2.end_idx)

        # 判断背驰
        if s1.direction == StrokeDirection.UP:
            # 上升笔比较
            price1 = s1.end_price
            price2 = s2.end_price

            # 价格创新高，但MACD柱子面积没创新高 → 顶背驰
            if price2 > price1 and abs(macd_area2) < abs(macd_area1):
                severity = abs(macd_area1 - macd_area2) / (abs(macd_area1) + 1e-10)
                divergences.append(Divergence(
                    divergence_type=DivergenceType.BEARISH,
                    price_extremum_idx=s2.end_idx + start_offset,
                    macd_extremum_idx=s2.end_idx + start_offset,
                    price_extremum_value=price2,
                    macd_extremum_value=macd_area2,
                    macd_prev_extremum_value=macd_area1,
                    price_prev_extremum_value=price1,
                    severity=min(severity, 1.0),
                    description=f"顶背驰: 价格{s1.end_price:.2f}→{price2:.2f}创新高, "
                                f"MACD {macd_area1:.4f}→{macd_area2:.4f}未新高",
                ))
        else:
            # 下降笔比较
            price1 = s1.end_price
            price2 = s2.end_price

            # 价格创新低，但MACD柱子面积没创新低 → 底背驰
            if price2 < price1 and abs(macd_area2) < abs(macd_area1):
                severity = abs(macd_area1 - macd_area2) / (abs(macd_area1) + 1e-10)
                divergences.append(Divergence(
                    divergence_type=DivergenceType.BULLISH,
                    price_extremum_idx=s2.end_idx + start_offset,
                    macd_extremum_idx=s2.end_idx + start_offset,
                    price_extremum_value=price2,
                    macd_extremum_value=macd_area2,
                    macd_prev_extremum_value=macd_area1,
                    price_prev_extremum_value=price1,
                    severity=min(severity, 1.0),
                    description=f"底背驰: 价格{s1.end_price:.2f}→{price2:.2f}创新低, "
                                f"MACD {macd_area1:.4f}→{macd_area2:.4f}未新低",
                ))

        i += 1

    return divergences


def _macd_area(histogram: np.ndarray, start_idx: int, end_idx: int) -> float:
    """
    计算区间内 MACD 柱子面积（积分）。
    
    正值区间: 累加正值
    负值区间: 累加负值
    """
    if start_idx < 0:
        start_idx = 0
    if end_idx >= len(histogram):
        end_idx = len(histogram) - 1
    if start_idx >= len(histogram):
        return 0.0

    window = histogram[start_idx:end_idx + 1]
    # 简化：用总和作为面积代理
    return float(np.nansum(window))


def get_latest_divergence(divergences: list[Divergence]) -> Optional[Divergence]:
    """获取最新的背驰信号."""
    if not divergences:
        return None
    return divergences[-1]
