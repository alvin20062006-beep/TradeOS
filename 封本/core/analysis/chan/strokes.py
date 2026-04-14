"""
笔构建模块 (Strokes)
=================

缠论第二步：从分型构建笔。

规则:
- 相邻的顶分型和底分型构成一笔
- 中间至少间隔 bi_min_bars (5) 根不重叠的K线
- 笔有方向: 上升笔(底→顶) / 下降笔(顶→底)
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .fractals import Fractal, FractalType, detect_fractals, fractal_to_bar_idx


class StrokeDirection(str, Enum):
    """笔方向."""
    UP = "up"    # 上升笔
    DOWN = "down"  # 下降笔


@dataclass
class Stroke:
    """笔结构."""
    direction: StrokeDirection
    start_idx: int       # 起始分型索引
    end_idx: int         # 结束分型索引
    start_price: float   # 起始价格（底分型=最低价，顶分型=最高价）
    end_price: float     # 结束价格
    height: float        # 笔的高度
    bar_count: int       # 包含的K线数（含分型K线）
    
    def __repr__(self):
        return (f"Stroke({self.direction.value}, "
                f"start={self.start_price:.2f}, end={self.end_price:.2f}, "
                f"height={self.height:.2f}, bars={self.bar_count})")


def build_strokes(
    fractals: list[Fractal],
    highs: np.ndarray,
    lows: np.ndarray,
    min_bars: int = 5,
) -> list[Stroke]:
    """
    从分型构建笔.
    
    Args:
        fractals: 分型列表
        highs: 最高价序列
        lows: 最低价序列
        min_bars: 中间最少K线数（不含分型K线，默认5）
        
    Returns:
        笔列表
    """
    if len(fractals) < 2:
        return []

    strokes = []
    i = 0
    
    while i < len(fractals) - 1:
        f1 = fractals[i]
        f2 = fractals[i + 1]
        
        # 必须相邻的顶底交替
        if f1.fractal_type == f2.fractal_type:
            i += 1
            continue
        
        # 计算中间K线数
        # 中间K线: 从f1.end_index之后到f2.start_index之前的K线
        middle_start = f1.end_index + 1
        middle_end = f2.start_index - 1
        middle_bars = max(0, middle_end - middle_start + 1)
        
        # 如果中间K线数不足，跳过这一对
        if middle_bars < min_bars:
            i += 1
            continue
        
        # 确定方向
        if f1.fractal_type == FractalType.BOTTOM:
            # 底 → 顶: 上升笔
            direction = StrokeDirection.UP
            start_price = f1.price
            end_price = f2.price
        else:
            # 顶 → 底: 下降笔
            direction = StrokeDirection.DOWN
            start_price = f1.price
            end_price = f2.price
        
        height = abs(end_price - start_price)
        bar_count = (f2.end_index - f1.start_index + 1)
        
        strokes.append(Stroke(
            direction=direction,
            start_idx=f1.index,
            end_idx=f2.index,
            start_price=start_price,
            end_price=end_price,
            height=height,
            bar_count=bar_count,
        ))
        
        i += 1
    
    return strokes


def validate_stroke(stroke: Stroke, prev_stroke: Optional[Stroke] = None) -> bool:
    """
    验证笔的有效性.
    
    Args:
        stroke: 待验证的笔
        prev_stroke: 前一笔（用于验证方向交替）
        
    Returns:
        True=有效, False=无效
    """
    # 高度必须 > 0
    if stroke.height <= 0:
        return False
    
    # 前一笔方向必须相反
    if prev_stroke is not None:
        if stroke.direction == prev_stroke.direction:
            return False
    
    return True


def get_stroke_endpoints(strokes: list[Stroke]) -> tuple[list[int], list[float]]:
    """
    获取笔的端点序列（用于后续线段构建）.
    
    Args:
        strokes: 笔列表
        
    Returns:
        (indices, prices) 端点索引和价格序列
    """
    indices = []
    prices = []
    
    for stroke in strokes:
        indices.append(stroke.start_idx)
        prices.append(stroke.start_price)
    
    if strokes:
        indices.append(strokes[-1].end_idx)
        prices.append(strokes[-1].end_price)
    
    return indices, prices


def stroke_price_range(stroke: Stroke) -> tuple[float, float]:
    """
    获取笔的价格区间.
    
    Args:
        stroke: 笔
        
    Returns:
        (low, high) 最低价和最高价
    """
    if stroke.direction == StrokeDirection.UP:
        return stroke.start_price, stroke.end_price
    else:
        return stroke.end_price, stroke.start_price
