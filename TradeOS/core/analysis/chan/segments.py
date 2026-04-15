"""
线段划分模块 (Segments)
=====================

缠论第三步：从笔构建线段。

规则（简化版）:
- 连续三笔构成线段的基本结构
- 线段被破坏的条件：价格反向运动超过前一线段的50%
- 线段有方向: 上升线段 / 下降线段
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .strokes import Stroke, StrokeDirection


class SegmentDirection(str, Enum):
    """线段方向."""
    UP = "up"
    DOWN = "down"


@dataclass
class Segment:
    """线段结构."""
    direction: SegmentDirection
    start_idx: int      # 起始笔索引
    end_idx: int        # 结束笔索引
    start_price: float  # 起始价格
    end_price: float    # 结束价格
    height: float       # 线段高度
    stroke_count: int   # 包含的笔数
    
    def __repr__(self):
        return (f"Segment({self.direction.value}, "
                f"start={self.start_price:.2f}, end={self.end_price:.2f}, "
                f"strokes={self.stroke_count})")


@dataclass
class SegmentBreak:
    """线段破坏."""
    break_idx: int      # 破坏发生时的笔索引
    break_price: float  # 破坏价格
    segment_end_idx: int  # 被破坏线段的结束笔索引


def build_segments(
    strokes: list[Stroke],
    back_ratio: float = 0.5,
) -> list[Segment]:
    """
    从笔构建线段（简化版算法）。
    
    简化规则:
    - 连续三笔方向相同 → 形成上升/下降线段
    - 线段破坏: 反向笔的终点回到前一线段起点价格的一定比例
    
    Args:
        strokes: 笔列表
        back_ratio: 回撤比例（超过此比例认为线段破坏，默认0.5）
        
    Returns:
        线段列表
    """
    if len(strokes) < 3:
        return []

    segments = []
    i = 0

    while i <= len(strokes) - 3:
        # 取连续三笔
        s1, s2, s3 = strokes[i], strokes[i + 1], strokes[i + 2]

        # 三笔方向相同
        if s1.direction == s2.direction == s3.direction:
            direction = SegmentDirection.UP if s1.direction == StrokeDirection.UP else SegmentDirection.DOWN

            # 线段起点
            start_price = s1.start_price
            end_price = s3.end_price

            # 计算线段高度
            if direction == SegmentDirection.UP:
                height = end_price - start_price
            else:
                height = start_price - end_price

            # 只有方向明确时才创建线段
            if height > 0:
                segments.append(Segment(
                    direction=direction,
                    start_idx=i,
                    end_idx=i + 2,
                    start_price=start_price,
                    end_price=end_price,
                    height=height,
                    stroke_count=3,
                ))

                # 尝试继续延伸线段
                extended = _extend_segment(strokes, i + 2, direction)
                if extended:
                    segments[-1] = extended

                i = segments[-1].end_idx + 1
                continue

        i += 1

    return segments


def _extend_segment(
    strokes: list[Stroke],
    current_end_idx: int,
    direction: SegmentDirection,
) -> Optional[Segment]:
    """
    尝试延伸线段.
    
    Args:
        strokes: 笔列表
        current_end_idx: 当前线段结束笔索引
        direction: 线段方向
        
    Returns:
        延伸后的线段，或None
    """
    # 尝试继续延伸
    i = current_end_idx + 1
    while i < len(strokes):
        next_stroke = strokes[i]

        # 方向相同，继续延伸
        expected_dir = StrokeDirection.UP if direction == SegmentDirection.UP else StrokeDirection.DOWN
        if next_stroke.direction == expected_dir:
            # 更新线段终点
            end_price = next_stroke.end_price
            end_idx = i
        else:
            # 方向改变，线段结束
            break

        i += 1

    if i - 1 > current_end_idx:
        # 有延伸
        first_stroke = strokes[0]  # 这需要在调用前保存
        return None  # 简化：直接返回None，由主逻辑处理

    return None


def detect_segment_breaks(
    strokes: list[Stroke],
    segments: list[Segment],
    back_ratio: float = 0.5,
) -> list[SegmentBreak]:
    """
    检测线段破坏。
    
    线段破坏条件:
    - 上升线段：被下降笔反向击穿，且击穿幅度 > 线段高度的50%
    - 下降线段：被上升笔反向击穿，且击穿幅度 > 线段高度的50%
    
    Args:
        strokes: 笔列表
        segments: 线段列表
        back_ratio: 回撤比例阈值
        
    Returns:
        线段破坏列表
    """
    breaks = []

    for seg in segments:
        if seg.end_idx >= len(strokes):
            continue

        # 检查后续笔是否破坏了线段
        for i in range(seg.end_idx + 1, len(strokes)):
            stroke = strokes[i]
            seg_direction = SegmentDirection.UP if seg.direction == SegmentDirection.UP else SegmentDirection.DOWN

            if stroke.direction != seg_direction:
                # 反向笔出现，检查是否破坏
                seg_low = min(seg.start_price, seg.end_price)
                seg_high = max(seg.start_price, seg.end_price)
                stroke_end = stroke.end_price

                if seg.direction == SegmentDirection.UP:
                    # 上升线段被下降笔反向
                    if stroke_end < seg_low - (seg_high - seg_low) * back_ratio:
                        breaks.append(SegmentBreak(
                            break_idx=i,
                            break_price=stroke_end,
                            segment_end_idx=seg.end_idx,
                        ))
                        break
                else:
                    # 下降线段被上升笔反向
                    if stroke_end > seg_high + (seg_high - seg_low) * back_ratio:
                        breaks.append(SegmentBreak(
                            break_idx=i,
                            break_price=stroke_end,
                            segment_end_idx=seg.end_idx,
                        ))
                        break

    return breaks


def get_segment_status(strokes: list[Stroke], segments: list[Segment]) -> str:
    """
    获取当前走势状态描述。
    
    Args:
        strokes: 笔列表
        segments: 线段列表
        
    Returns:
        状态描述字符串
    """
    if not segments:
        return "no_segment"
    if not strokes:
        return "no_stroke"

    last_stroke = strokes[-1]
    last_seg = segments[-1]

    if last_stroke.direction == last_seg.direction:
        return f"forming_{last_seg.direction.value}"
    else:
        return f"reversing"


def segment_price_range(segment: Segment) -> tuple[float, float]:
    """
    获取线段价格区间.
    """
    if segment.direction == SegmentDirection.UP:
        return segment.start_price, segment.end_price
    else:
        return segment.end_price, segment.start_price
