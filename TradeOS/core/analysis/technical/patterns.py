"""
图表形态识别模块
===============

包含:
- 头肩顶/底
- 双顶/双底
- 三角形 (上升/下降/对称)
"""

from __future__ import annotations

import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class Pattern:
    """形态识别结果."""
    name: str
    direction: str  # "bullish" / "bearish" / "neutral"
    confidence: float
    start_idx: int
    end_idx: int
    neckline: Optional[float] = None


def find_local_extrema(prices: np.ndarray, window: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """
    找到局部高点和低点.
    
    Args:
        prices: 价格序列
        window: 窗口大小 (默认 5)
        
    Returns:
        (highs_idx, lows_idx) 局部高/低点索引
    """
    n = len(prices)
    highs = []
    lows = []
    
    for i in range(window, n - window):
        # 局部高点
        if all(prices[i] > prices[i - j] for j in range(1, window + 1)) and \
           all(prices[i] >= prices[i + j] for j in range(1, window + 1)):
            highs.append(i)
        # 局部低点
        if all(prices[i] < prices[i - j] for j in range(1, window + 1)) and \
           all(prices[i] <= prices[i + j] for j in range(1, window + 1)):
            lows.append(i)
    
    return np.array(highs), np.array(lows)


def detect_head_shoulders(
    prices: np.ndarray,
    window: int = 5,
    tolerance: float = 0.03,
) -> list[Pattern]:
    """
    头肩顶/底形态识别.
    
    Args:
        prices: 价格序列
        window: 极值点窗口
        tolerance: 肩部高度允许误差 (默认 3%)
        
    Returns:
        识别到的形态列表
    """
    patterns = []
    highs, lows = find_local_extrema(prices, window)
    
    # 头肩顶 (顶部反转)
    for i in range(2, len(highs)):
        left_shoulder = highs[i - 2]
        head = highs[i - 1]
        right_shoulder = highs[i]
        
        if head >= left_shoulder and head >= right_shoulder:
            # 两肩高度接近
            ls_price = prices[left_shoulder]
            h_price = prices[head]
            rs_price = prices[right_shoulder]
            
            if abs(ls_price - rs_price) / max(ls_price, rs_price) < tolerance:
                # 计算颈线 (两肩之间的低点连线)
                neckline_region = prices[left_shoulder : right_shoulder + 1]
                neckline = np.min(neckline_region)
                
                confidence = min(0.9, 0.5 + (h_price - neckline) / h_price)
                
                patterns.append(Pattern(
                    name="head_and_shoulders_top",
                    direction="bearish",
                    confidence=confidence,
                    start_idx=left_shoulder,
                    end_idx=right_shoulder,
                    neckline=neckline,
                ))
    
    # 头肩底 (底部反转)
    for i in range(2, len(lows)):
        left_shoulder = lows[i - 2]
        head = lows[i - 1]
        right_shoulder = lows[i]
        
        if head <= left_shoulder and head <= right_shoulder:
            ls_price = prices[left_shoulder]
            h_price = prices[head]
            rs_price = prices[right_shoulder]
            
            if abs(ls_price - rs_price) / max(ls_price, rs_price) < tolerance:
                neckline_region = prices[left_shoulder : right_shoulder + 1]
                neckline = np.max(neckline_region)
                
                confidence = min(0.9, 0.5 + (neckline - h_price) / neckline)
                
                patterns.append(Pattern(
                    name="head_and_shoulders_bottom",
                    direction="bullish",
                    confidence=confidence,
                    start_idx=left_shoulder,
                    end_idx=right_shoulder,
                    neckline=neckline,
                ))
    
    return patterns


def detect_double_top_bottom(
    prices: np.ndarray,
    window: int = 5,
    tolerance: float = 0.02,
) -> list[Pattern]:
    """
    双顶/双底形态识别.
    
    Args:
        prices: 价格序列
        window: 极值点窗口
        tolerance: 高度允许误差 (默认 2%)
        
    Returns:
        识别到的形态列表
    """
    patterns = []
    highs, lows = find_local_extrema(prices, window)
    
    # 双顶
    for i in range(1, len(highs)):
        peak1 = highs[i - 1]
        peak2 = highs[i]
        
        p1_price = prices[peak1]
        p2_price = prices[peak2]
        
        if abs(p1_price - p2_price) / max(p1_price, p2_price) < tolerance:
            valley_region = prices[peak1 : peak2 + 1]
            neckline = np.min(valley_region)
            
            confidence = min(0.85, 0.5 + (p1_price - neckline) / p1_price * 2)
            
            patterns.append(Pattern(
                name="double_top",
                direction="bearish",
                confidence=confidence,
                start_idx=peak1,
                end_idx=peak2,
                neckline=neckline,
            ))
    
    # 双底
    for i in range(1, len(lows)):
        bottom1 = lows[i - 1]
        bottom2 = lows[i]
        
        b1_price = prices[bottom1]
        b2_price = prices[bottom2]
        
        if abs(b1_price - b2_price) / max(b1_price, b2_price) < tolerance:
            peak_region = prices[bottom1 : bottom2 + 1]
            neckline = np.max(peak_region)
            
            confidence = min(0.85, 0.5 + (neckline - b1_price) / neckline * 2)
            
            patterns.append(Pattern(
                name="double_bottom",
                direction="bullish",
                confidence=confidence,
                start_idx=bottom1,
                end_idx=bottom2,
                neckline=neckline,
            ))
    
    return patterns


def detect_triangles(
    prices: np.ndarray,
    window: int = 5,
    min_points: int = 4,
) -> list[Pattern]:
    """
    三角形形态识别 (上升/下降/对称).
    
    Args:
        prices: 价格序列
        window: 极值点窗口
        min_points: 最少需要 4 个极值点
        
    Returns:
        识别到的形态列表
    """
    patterns = []
    highs, lows = find_local_extrema(prices, window)
    
    # 至少需要 4 个极值点
    if len(highs) < min_points // 2 or len(lows) < min_points // 2:
        return patterns
    
    # 简化实现: 检测收敛的波动
    # 取最近的极值点进行分析
    recent_len = min(10, len(highs))
    recent_highs = highs[-recent_len:]
    recent_lows = lows[-recent_len:]
    
    if len(recent_highs) >= 2 and len(recent_lows) >= 2:
        # 高点趋势
        high_prices = prices[recent_highs]
        low_prices = prices[recent_lows]
        
        high_trend = np.polyfit(range(len(high_prices)), high_prices, 1)[0] if len(high_prices) > 1 else 0
        low_trend = np.polyfit(range(len(low_prices)), low_prices, 1)[0] if len(low_prices) > 1 else 0
        
        # 上升三角形: 高点水平, 低点上升
        if abs(high_trend) < 0.01 * np.mean(high_prices) and low_trend > 0:
            patterns.append(Pattern(
                name="ascending_triangle",
                direction="bullish",
                confidence=0.7,
                start_idx=min(recent_highs[0], recent_lows[0]),
                end_idx=max(recent_highs[-1], recent_lows[-1]),
            ))
        # 下降三角形: 低点水平, 高点下降
        elif abs(low_trend) < 0.01 * np.mean(low_prices) and high_trend < 0:
            patterns.append(Pattern(
                name="descending_triangle",
                direction="bearish",
                confidence=0.7,
                start_idx=min(recent_highs[0], recent_lows[0]),
                end_idx=max(recent_highs[-1], recent_lows[-1]),
            ))
        # 对称三角形: 高点下降, 低点上升
        elif high_trend < 0 and low_trend > 0:
            patterns.append(Pattern(
                name="symmetric_triangle",
                direction="neutral",
                confidence=0.6,
                start_idx=min(recent_highs[0], recent_lows[0]),
                end_idx=max(recent_highs[-1], recent_lows[-1]),
            ))
    
    return patterns


def scan_patterns(prices: np.ndarray, window: int = 5) -> list[Pattern]:
    """
    扫描所有形态.
    
    Args:
        prices: 价格序列
        window: 极值点窗口
        
    Returns:
        所有识别到的形态列表
    """
    patterns = []
    patterns.extend(detect_head_shoulders(prices, window))
    patterns.extend(detect_double_top_bottom(prices, window))
    patterns.extend(detect_triangles(prices, window))
    
    # 按置信度排序
    patterns.sort(key=lambda p: p.confidence, reverse=True)
    
    return patterns
