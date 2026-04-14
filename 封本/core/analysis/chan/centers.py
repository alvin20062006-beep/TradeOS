"""
中枢识别模块 (Centers)
====================

缠论第四步：从线段构建中枢。

规则（简化版）:
- 三段有重叠的价格区间 → 构成中枢
- 中枢区间: [GG, DD] (高中取高为GG，抵中取低为DD)
- 中枢方向: 由进入段和离开段的方向决定
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple

from .segments import Segment, SegmentDirection


@dataclass
class Center:
    """
    中枢结构.
    
    属性:
        index: 中枢序号
        start_idx: 起始线段索引
        end_idx: 结束线段索引
        gg: 中枢区间高点（高中取高）
        dd: 中枢区间低点（抵中取低）
        zg: 中枢上沿
        zd: 中枢下沿
        height: 中枢高度
        direction: 中枢方向
    """
    index: int
    start_idx: int
    end_idx: int
    gg: float   # 中枢区间高点
    dd: float   # 中枢区间低点
    zg: float   # 中枢上沿 = gg
    zd: float   # 中枢下沿 = dd
    height: float
    direction: str  # "up" / "down"

    @property
    def range(self) -> Tuple[float, float]:
        """中枢区间 (zd, zg)."""
        return self.zd, self.zg

    @property
    def mid(self) -> float:
        """中枢中点."""
        return (self.zg + self.zd) / 2

    def __repr__(self):
        return (f"Center(#{self.index}, [{self.zd:.2f}, {self.zg:.2f}], "
                f"h={self.height:.2f}, dir={self.direction})")


def _segment_range(segment: Segment) -> Tuple[float, float]:
    """获取线段的价格区间 (low, high)."""
    return segment.start_price, segment.end_price


def build_centers(
    segments: list[Segment],
    min_overlap: int = 3,
) -> list[Center]:
    """
    从线段构建中枢（简化版算法）。

    规则:
    - 连续3段存在重叠区间 → 形成中枢
    - 中枢区间: 取三段高低点的交集

    Args:
        segments: 线段列表
        min_overlap: 最少重叠线段数（默认3）

    Returns:
        中枢列表
    """
    if len(segments) < min_overlap:
        return []

    centers: list[Center] = []
    center_idx = 0
    i = 0

    while i <= len(segments) - min_overlap:
        # 取连续三段
        s1, s2, s3 = segments[i], segments[i + 1], segments[i + 2]

        # 获取每段的高低点
        r1 = _segment_range(s1)
        r2 = _segment_range(s2)
        r3 = _segment_range(s3)

        # 三段方向交替: s1↑ s2↓ s3↑ (或 s1↓ s2↑ s3↓)
        # 计算重叠区间
        seg_dirs = [s.direction for s in [s1, s2, s3]]
        
        # 重叠区间: max(lows) ~ min(highs)
        lows = [min(r1), min(r2), min(r3)]
        highs = [max(r1), max(r2), max(r3)]
        
        overlap_high = min(highs)  # 三段高点中的最低者
        overlap_low = max(lows)   # 三段低点中的最高者

        # 有有效重叠: overlap_low < overlap_high
        if overlap_low < overlap_high:
            # 计算中枢方向: 由第一段和第三段的方向决定
            # 如果第一段和第三段方向相同 → 有方向
            if s1.direction == s3.direction:
                direction = "up" if s1.direction == SegmentDirection.UP else "down"
            else:
                direction = "neutral"

            center_height = overlap_high - overlap_low

            centers.append(Center(
                index=center_idx,
                start_idx=i,
                end_idx=i + 2,
                gg=overlap_high,
                dd=overlap_low,
                zg=overlap_high,
                zd=overlap_low,
                height=center_height,
                direction=direction,
            ))
            center_idx += 1

            # 中枢构成后，尝试延伸（看后续段是否仍在中枢内）
            extended_end = _extend_center(segments, i + 3, overlap_low, overlap_high)
            if extended_end > i + 2:
                # 更新中枢结束索引
                centers[-1] = _update_center_end(centers[-1], segments, extended_end)

            i = extended_end + 1
            continue

        i += 1

    return centers


def _extend_center(
    segments: list[Segment],
    start: int,
    zd: float,
    zg: float,
) -> int:
    """
    尝试延伸中枢。
    
    看后续线段是否仍落在[zd, zg]区间内。
    只要线段的高点和低点都在中枢内，就继续延伸。
    
    Returns:
        延伸到的结束索引
    """
    end = start
    while end < len(segments):
        seg = segments[end]
        s_low = min(seg.start_price, seg.end_price)
        s_high = max(seg.start_price, seg.end_price)
        
        # 线段完全在中枢内 → 延伸
        if s_low >= zd and s_high <= zg:
            end += 1
        else:
            break
    
    return end - 1


def _update_center_end(center: Center, segments: list[Segment], new_end: int) -> Center:
    """更新中枢的结束索引."""
    # 重新计算中枢区间（如果有更多段加入）
    segs_in_center = segments[center.start_idx : new_end + 1]
    
    if len(segs_in_center) < 3:
        center.end_idx = new_end
        return center
    
    # 取前三段计算基础区间，后续段检查是否在区间内
    lows = []
    highs = []
    for s in segs_in_center:
        r = _segment_range(s)
        lows.append(min(r))
        highs.append(max(r))
    
    overlap_high = min(highs[:3])
    overlap_low = max(lows[:3])
    
    # 检查后续段是否在区间内
    for i in range(3, len(segs_in_center)):
        r = _segment_range(segs_in_center[i])
        # 只要没有完全离开，就继续延伸
        s_low, s_high = min(r), max(r)
    
    center.end_idx = new_end
    return center


def get_latest_center(centers: list[Center]) -> Optional[Center]:
    """获取最新（最后一个）中枢."""
    if not centers:
        return None
    return centers[-1]


def is_price_in_center(price: float, center: Center) -> bool:
    """判断价格是否在中枢内."""
    return center.zd <= price <= center.zg


def is_price_above_center(price: float, center: Center) -> bool:
    """判断价格是否在中枢上方."""
    return price > center.zg


def is_price_below_center(price: float, center: Center) -> bool:
    """判断价格是否在中枢下方."""
    return price < center.zd


def center_status(centers: list[Center], current_price: float) -> str:
    """
    判断当前价格与中枢的关系状态。
    
    Returns:
        "in_center" / "above_center" / "below_center" / "no_center"
    """
    if not centers:
        return "no_center"
    
    latest = centers[-1]
    
    if is_price_in_center(current_price, latest):
        return "in_center"
    elif is_price_above_center(current_price, latest):
        return "above_center"
    else:
        return "below_center"


def summarize_centers(centers: list[Center]) -> dict:
    """
    汇总中枢信息。
    
    Returns:
        中枢汇总字典
    """
    if not centers:
        return {"count": 0, "summary": "no_center"}

    latest = centers[-1]
    return {
        "count": len(centers),
        "latest": {
            "index": latest.index,
            "range": f"[{latest.zd:.2f}, {latest.zg:.2f}]",
            "direction": latest.direction,
            "height": latest.height,
        },
        "all_ranges": [f"[{c.zd:.2f}, {c.zg:.2f}]" for c in centers],
    }
