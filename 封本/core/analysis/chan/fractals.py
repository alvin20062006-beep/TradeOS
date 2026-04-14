"""
分型识别模块 (Fractals)
=====================

缠论第一步：识别顶分型和底分型。

定义:
- 顶分型：三根相邻K线，中间一根的最高价最高
- 底分型：三根相邻K线，中间一根的最低价最低

包含处理:
- 包含关系处理（吞并）：上升K线和下降K线的包含
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FractalType(str, Enum):
    """分型类型."""
    TOP = "top"      # 顶分型
    BOTTOM = "bottom"  # 底分型


@dataclass
class Fractal:
    """分型结构."""
    fractal_type: FractalType
    index: int            # 中间那根K线在原始序列中的索引
    start_index: int      # 三根K线的起始索引
    end_index: int        # 三根K线的结束索引
    price: float          # 分型价格（顶分型=最高价，底分型=最低价）
    
    def __repr__(self):
        return f"Fractal({self.fractal_type.value}, idx={self.index}, price={self.price:.2f})"


def _is_bullish_bar(opens: np.ndarray, closes: np.ndarray, i: int) -> bool:
    """第i根K线是阳线."""
    return closes[i] >= opens[i]


def _is_bearish_bar(opens: np.ndarray, closes: np.ndarray, i: int) -> bool:
    """第i根K线是阴线."""
    return closes[i] < opens[i]


def _handle_inclusion(
    highs: np.ndarray,
    lows: np.ndarray,
    opens: np.ndarray,
    closes: np.ndarray,
) -> tuple[list[int], list[int], list[int]]:
    """
    处理K线的包含关系（缠论第三K线包含处理）。
    
    规则:
    1. 阳线（收高于开）包含：取两根K线的高点最高、低点最高
    2. 阴线（收低于开）包含：取两根K线的高点最低、低点最低
    
    Args:
        highs: 最高价序列
        lows: 最低价序列
        opens: 开盘价序列
        closes: 收盘价序列
        
    Returns:
        (processed_highs, processed_lows, processed_indices)
        处理后的高点序列、低点序列、对应原始索引
    """
    n = len(highs)
    processed_highs = []
    processed_lows = []
    processed_indices = []
    
    i = 0
    while i < n:
        if i + 1 < n and i + 2 < n:
            # 看前三根K线
            h1, l1 = highs[i], lows[i]
            h2, l2 = highs[i + 1], lows[i + 1]
            
            # 判断是否有包含关系
            # 上升趋势中：第二根K线高点 > 第一根高点 且 低点 >= 第一根低点
            # 下降趋势中：第二根K线高点 <= 第一根高点 且 低点 < 第一根低点
            up_trend = h2 > h1 and l2 >= l1
            down_trend = h2 <= h1 and l2 < l1
            
            if up_trend or down_trend:
                # 有包含关系，合并
                if up_trend:
                    # 阳包阴：取高点最高、低点最高
                    merged_high = max(h1, h2)
                    merged_low = max(l1, l2)
                else:
                    # 阴包阳：取高点最低、低点最低
                    merged_high = min(h1, h2)
                    merged_low = min(l1, l2)
                
                # 处理合并后的K线与第三根的包含关系
                if i + 2 < n:
                    h3, l3 = highs[i + 2], lows[i + 2]
                    merged_high2 = merged_high
                    merged_low2 = merged_low
                    
                    # 继续处理包含
                    while i + 2 < n:
                        h3, l3 = highs[i + 2], lows[i + 2]
                        # 检查是否仍有包含
                        if h3 > merged_high2 and l3 >= merged_low2:
                            merged_high2 = h3
                        elif h3 <= merged_high2 and l3 < merged_low2:
                            merged_low2 = l3
                        else:
                            break
                        i += 1
                    
                    processed_highs.append(merged_high2)
                    processed_lows.append(merged_low2)
                    processed_indices.append(i)
            else:
                processed_highs.append(h1)
                processed_lows.append(l1)
                processed_indices.append(i)
        else:
            processed_highs.append(highs[i])
            processed_lows.append(lows[i])
            processed_indices.append(i)
        
        i += 1
    
    return processed_highs, processed_lows, processed_indices


def detect_fractals_basic(
    highs: np.ndarray,
    lows: np.ndarray,
    opens: np.ndarray,
    closes: np.ndarray,
    min_bars: int = 3,
) -> list[Fractal]:
    """
    最基本的分型识别（不做包含处理）。

    Args:
        highs: 最高价序列
        lows: 最低价序列
        opens: 开盘价序列
        closes: 收盘价序列
        min_bars: 最少K线数（默认3）

    Returns:
        分型列表
    """
    if len(highs) < min_bars:
        return []

    fractals = []

    for i in range(1, len(highs) - 1):
        prev_high, curr_high, next_high = highs[i - 1], highs[i], highs[i + 1]
        prev_low, curr_low, next_low = lows[i - 1], lows[i], lows[i + 1]

        # 顶分型：中间K线最高
        if curr_high > prev_high and curr_high > next_high:
            fractals.append(Fractal(
                fractal_type=FractalType.TOP,
                index=i,
                start_index=i - 1,
                end_index=i + 1,
                price=curr_high,
            ))

        # 底分型：中间K线最低
        elif curr_low < prev_low and curr_low < next_low:
            fractals.append(Fractal(
                fractal_type=FractalType.BOTTOM,
                index=i,
                start_index=i - 1,
                end_index=i + 1,
                price=curr_low,
            ))

    return fractals


def detect_fractals(
    highs: np.ndarray,
    lows: np.ndarray,
    opens: np.ndarray,
    closes: np.ndarray,
    handle_inclusion: bool = True,
    min_bars: int = 3,
) -> list[Fractal]:
    """
    完整的分型识别（含包含处理）。

    Args:
        highs: 最高价序列
        lows: 最低价序列
        opens: 开盘价序列
        closes: 收盘价序列
        handle_inclusion: 是否处理包含关系（默认True）
        min_bars: 最少K线数

    Returns:
        分型列表
    """
    if handle_inclusion:
        proc_highs, proc_lows, proc_indices = _handle_inclusion(
            highs, lows, opens, closes
        )
        # 用处理后的数据重新识别分型
        if len(proc_highs) >= min_bars:
            proc_highs_arr = np.array(proc_highs)
            proc_lows_arr = np.array(proc_lows)
            
            fractals = []
            for i in range(1, len(proc_highs_arr) - 1):
                # 顶分型
                if proc_highs_arr[i] > proc_highs_arr[i - 1] and proc_highs_arr[i] > proc_highs_arr[i + 1]:
                    orig_idx = proc_indices[i]
                    fractals.append(Fractal(
                        fractal_type=FractalType.TOP,
                        index=orig_idx,
                        start_index=proc_indices[i - 1],
                        end_index=proc_indices[i + 1],
                        price=proc_highs_arr[i],
                    ))
                # 底分型
                elif proc_lows_arr[i] < proc_lows_arr[i - 1] and proc_lows_arr[i] < proc_lows_arr[i + 1]:
                    orig_idx = proc_indices[i]
                    fractals.append(Fractal(
                        fractal_type=FractalType.BOTTOM,
                        index=orig_idx,
                        start_index=proc_indices[i - 1],
                        end_index=proc_indices[i + 1],
                        price=proc_lows_arr[i],
                    ))
            return fractals
    
    return detect_fractals_basic(highs, lows, opens, closes, min_bars)


def fractal_to_bar_idx(fractals: list[Fractal]) -> tuple[list[int], list[int]]:
    """
    提取分型的顶底索引序列。
    
    Args:
        fractals: 分型列表
        
    Returns:
        (top_indices, bottom_indices) 顶/底分型对应的K线索引
    """
    tops = [f.index for f in fractals if f.fractal_type == FractalType.TOP]
    bottoms = [f.index for f in fractals if f.fractal_type == FractalType.BOTTOM]
    return tops, bottoms
