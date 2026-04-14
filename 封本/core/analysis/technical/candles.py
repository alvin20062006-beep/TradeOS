"""
K线形态识别模块
===============

包含:
- 吞没形态 (看涨/看跌)
- 十字星
- 锤头线/上吊线
- pin bar
- 孕线
"""

from __future__ import annotations

import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class CandlePattern:
    """K线形态识别结果."""
    name: str
    direction: str  # "bullish" / "bearish" / "neutral"
    confidence: float
    idx: int


def body_size(open_p: float, close: float) -> float:
    """实体大小."""
    return abs(close - open_p)


def upper_shadow(open_p: float, close: float, high: float) -> float:
    """上影线."""
    return high - max(open_p, close)


def lower_shadow(open_p: float, close: float, low: float) -> float:
    """下影线."""
    return min(open_p, close) - low


def is_bullish(open_p: float, close: float) -> bool:
    """是否阳线."""
    return close > open_p


def is_bearish(open_p: float, close: float) -> bool:
    """是否阴线."""
    return close < open_p


def detect_engulfing(
    opens: np.ndarray,
    closes: np.ndarray,
    min_body_ratio: float = 0.5,
) -> list[CandlePattern]:
    """
    吞没形态识别.
    
    看涨吞没: 前一根阴线, 当日阳线实体完全覆盖前一根实体
    看跌吞没: 前一根阳线, 当日阴线实体完全覆盖前一根实体
    
    Args:
        opens: 开盘价序列
        closes: 收盘价序列
        min_body_ratio: 当日实体至少是前一根的多少倍 (默认 0.5)
        
    Returns:
        识别到的形态列表
    """
    patterns = []
    n = len(opens)
    
    for i in range(1, n):
        prev_open, prev_close = opens[i - 1], closes[i - 1]
        curr_open, curr_close = opens[i], closes[i]
        
        prev_body = body_size(prev_open, prev_close)
        curr_body = body_size(curr_open, curr_close)
        
        if prev_body < 1e-6 or curr_body < 1e-6:
            continue
        
        # 看涨吞没
        if is_bearish(prev_open, prev_close) and is_bullish(curr_open, curr_close):
            # 当日阳线完全吞没前一日阴线
            if curr_open <= prev_close and curr_close >= prev_open:
                if curr_body >= prev_body * min_body_ratio:
                    patterns.append(CandlePattern(
                        name="bullish_engulfing",
                        direction="bullish",
                        confidence=min(0.9, 0.6 + curr_body / prev_body * 0.3),
                        idx=i,
                    ))
        
        # 看跌吞没
        elif is_bullish(prev_open, prev_close) and is_bearish(curr_open, curr_close):
            if curr_open >= prev_close and curr_close <= prev_open:
                if curr_body >= prev_body * min_body_ratio:
                    patterns.append(CandlePattern(
                        name="bearish_engulfing",
                        direction="bearish",
                        confidence=min(0.9, 0.6 + curr_body / prev_body * 0.3),
                        idx=i,
                    ))
    
    return patterns


def detect_doji(
    opens: np.ndarray,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    body_threshold: float = 0.1,
) -> list[CandlePattern]:
    """
    十字星识别.
    
    实体非常小, 上下影线较长的K线
    
    Args:
        opens: 开盘价序列
        closes: 收盘价序列
        highs: 最高价序列
        lows: 最低价序列
        body_threshold: 实体占整根K线比例阈值 (默认 10%)
        
    Returns:
        识别到的形态列表
    """
    patterns = []
    n = len(opens)
    
    for i in range(n):
        total_range = highs[i] - lows[i]
        if total_range < 1e-6:
            continue
        
        b_size = body_size(opens[i], closes[i])
        body_ratio = b_size / total_range
        
        if body_ratio < body_threshold:
            # 判断类型
            upper = upper_shadow(opens[i], closes[i], highs[i])
            lower = lower_shadow(opens[i], closes[i], lows[i])
            
            # 长腿十字星
            if upper > total_range * 0.3 and lower > total_range * 0.3:
                patterns.append(CandlePattern(
                    name="doji_long_leg",
                    direction="neutral",
                    confidence=0.7,
                    idx=i,
                ))
            # 蜻蜓十字星
            elif lower > total_range * 0.5:
                patterns.append(CandlePattern(
                    name="doji_dragonfly",
                    direction="bullish",
                    confidence=0.75,
                    idx=i,
                ))
            # 墓碑十字星
            elif upper > total_range * 0.5:
                patterns.append(CandlePattern(
                    name="doji_gravestone",
                    direction="bearish",
                    confidence=0.75,
                    idx=i,
                ))
            else:
                patterns.append(CandlePattern(
                    name="doji",
                    direction="neutral",
                    confidence=0.65,
                    idx=i,
                ))
    
    return patterns


def detect_hammer_hanging(
    opens: np.ndarray,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    shadow_ratio: float = 2.0,
) -> list[CandlePattern]:
    """
    锤头线/上吊线识别.
    
    下影线长, 实体小, 几乎没有上影线
    
    Args:
        opens: 开盘价序列
        closes: 收盘价序列
        highs: 最高价序列
        lows: 最低价序列
        shadow_ratio: 下影线至少是实体的多少倍 (默认 2)
        
    Returns:
        识别到的形态列表
    """
    patterns = []
    n = len(opens)
    
    for i in range(n):
        total_range = highs[i] - lows[i]
        if total_range < 1e-6:
            continue
        
        b_size = body_size(opens[i], closes[i])
        upper = upper_shadow(opens[i], closes[i], highs[i])
        lower = lower_shadow(opens[i], closes[i], lows[i])
        
        if b_size < 1e-6:
            continue
        
        # 下影线长, 上影线短, 实体小
        if lower >= b_size * shadow_ratio and upper < b_size * 0.5:
            # 判断是锤头线还是上吊线 (需要趋势上下文)
            if i > 0:
                prev_close = closes[i - 1]
                # 在下跌趋势后出现 → 锤头线 (看涨)
                if i > 5:
                    recent_trend = closes[i - 5 : i].mean()
                    if closes[i] < recent_trend:
                        patterns.append(CandlePattern(
                            name="hammer",
                            direction="bullish",
                            confidence=0.75,
                            idx=i,
                        ))
                        continue
                
                # 在上涨趋势后出现 → 上吊线 (看跌)
                if i > 5:
                    recent_trend = closes[i - 5 : i].mean()
                    if closes[i] > recent_trend:
                        patterns.append(CandlePattern(
                            name="hanging_man",
                            direction="bearish",
                            confidence=0.7,
                            idx=i,
                        ))
                        continue
            
            # 默认标记为锤头线
            patterns.append(CandlePattern(
                name="hammer_like",
                direction="bullish",
                confidence=0.65,
                idx=i,
            ))
    
    return patterns


def detect_pin_bar(
    opens: np.ndarray,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    nose_ratio: float = 0.3,
) -> list[CandlePattern]:
    """
    Pin bar 识别.
    
    典型的反转信号: 长影线 + 小实体
    
    Args:
        opens: 开盘价序列
        closes: 收盘价序列
        highs: 最高价序列
        lows: 最低价序列
        nose_ratio: 鼻子 (影线) 占整根K线比例 (默认 30%)
        
    Returns:
        识别到的形态列表
    """
    patterns = []
    n = len(opens)
    
    for i in range(n):
        total_range = highs[i] - lows[i]
        if total_range < 1e-6:
            continue
        
        b_size = body_size(opens[i], closes[i])
        upper = upper_shadow(opens[i], closes[i], highs[i])
        lower = lower_shadow(opens[i], closes[i], lows[i])
        
        # 看涨 pin bar: 长下影线, 实体在上部
        if lower >= total_range * nose_ratio and b_size < total_range * 0.35:
            if lower > upper * 2:
                patterns.append(CandlePattern(
                    name="bullish_pin_bar",
                    direction="bullish",
                    confidence=0.8,
                    idx=i,
                ))
        
        # 看跌 pin bar: 长上影线, 实体在下部
        elif upper >= total_range * nose_ratio and b_size < total_range * 0.35:
            if upper > lower * 2:
                patterns.append(CandlePattern(
                    name="bearish_pin_bar",
                    direction="bearish",
                    confidence=0.8,
                    idx=i,
                ))
    
    return patterns


def detect_harami(
    opens: np.ndarray,
    closes: np.ndarray,
) -> list[CandlePattern]:
    """
    孕线识别.
    
    前一根大K线, 当日小K线实体在前一根实体范围内
    
    Args:
        opens: 开盘价序列
        closes: 收盘价序列
        
    Returns:
        识别到的形态列表
    """
    patterns = []
    n = len(opens)
    
    for i in range(1, n):
        prev_open, prev_close = opens[i - 1], closes[i - 1]
        curr_open, curr_close = opens[i], closes[i]
        
        prev_body = body_size(prev_open, prev_close)
        curr_body = body_size(curr_open, curr_close)
        
        if prev_body < 1e-6:
            continue
        
        # 当日实体在前一日实体范围内
        prev_high = max(prev_open, prev_close)
        prev_low = min(prev_open, prev_close)
        curr_high = max(curr_open, curr_close)
        curr_low = min(curr_open, curr_close)
        
        if curr_high <= prev_high and curr_low >= prev_low:
            # 看涨孕线: 前一日阴线, 当日阳线
            if is_bearish(prev_open, prev_close) and is_bullish(curr_open, curr_close):
                patterns.append(CandlePattern(
                    name="bullish_harami",
                    direction="bullish",
                    confidence=0.7,
                    idx=i,
                ))
            # 看跌孕线: 前一日阳线, 当日阴线
            elif is_bullish(prev_open, prev_close) and is_bearish(curr_open, curr_close):
                patterns.append(CandlePattern(
                    name="bearish_harami",
                    direction="bearish",
                    confidence=0.7,
                    idx=i,
                ))
            # 十字孕线
            elif curr_body < prev_body * 0.1:
                patterns.append(CandlePattern(
                    name="harami_doji",
                    direction="neutral",
                    confidence=0.65,
                    idx=i,
                ))
    
    return patterns


def scan_candle_patterns(
    opens: np.ndarray,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
) -> list[CandlePattern]:
    """
    扫描所有K线形态.
    
    Args:
        opens: 开盘价序列
        closes: 收盘价序列
        highs: 最高价序列
        lows: 最低价序列
        
    Returns:
        所有识别到的形态列表
    """
    patterns = []
    patterns.extend(detect_engulfing(opens, closes))
    patterns.extend(detect_doji(opens, closes, highs, lows))
    patterns.extend(detect_hammer_hanging(opens, closes, highs, lows))
    patterns.extend(detect_pin_bar(opens, closes, highs, lows))
    patterns.extend(detect_harami(opens, closes))
    
    # 按置信度排序
    patterns.sort(key=lambda p: p.confidence, reverse=True)
    
    return patterns
