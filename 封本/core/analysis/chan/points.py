"""
买卖点判定模块 (Trading Points)
============================

缠论买卖点判定。

买卖点定义（简化版）:
- 一买（1st Purchase）: 底背驰后，第一个上升笔的起点
- 二买（2nd Purchase）: 回调不破一买低点的次低点
- 三买（3rd Purchase）: 离开中枢后，回调不破中枢上沿

- 一卖（1st Sell）: 顶背驰后，第一个下降笔的起点
- 二卖（2nd Sell）: 反弹不破一卖高点的次高点
- 三卖（3rd Sell）: 离开中枢后，反弹不破中枢下沿

结构失效:
- 下跌走势中，价格创出新低但没有背驰 → 结构失效（空头延续）
- 上涨走势中，价格创出新低但没有背驰 → 结构失效（多头延续）
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .strokes import Stroke, StrokeDirection
from .segments import Segment, SegmentDirection
from .centers import Center
from .divergence import Divergence, DivergenceType


class TradingPointType(str, Enum):
    """买卖点类型."""
    # 买点
    PURCHASE_1 = "1st_purchase"   # 一买（底背驰后）
    PURCHASE_2 = "2nd_purchase"  # 二买（次低点）
    PURCHASE_3 = "3rd_purchase"  # 三买（回抽不破中枢上沿）
    
    # 卖点
    SELL_1 = "1st_sell"          # 一卖（顶背驰后）
    SELL_2 = "2nd_sell"          # 二卖（次高点）
    SELL_3 = "3rd_sell"          # 三卖（反弹不破中枢下沿）
    
    # 特殊
    STRUCTURE_INVALID = "structure_invalid"  # 结构失效


@dataclass
class TradingPoint:
    """买卖点结构."""
    point_type: TradingPointType
    price: float
    index: int           # 对应的K线索引
    confidence: float    # 置信度 0-1
    related_center: Optional[int] = None  # 相关中枢序号
    stop_loss: Optional[float] = None   # 建议止损
    description: str = ""

    def __repr__(self):
        return (f"TradingPoint({self.point_type.value}, "
                f"price={self.price:.2f}, conf={self.confidence:.2f})")


@dataclass
class StructureState:
    """当前走势结构状态."""
    trend: str                    # "uptrend" / "downtrend" / "ranging"
    structure_valid: bool         # 结构是否有效
    invalidation_reason: Optional[str] = None
    latest_divergence: Optional[Divergence] = None
    latest_center: Optional[Center] = None
    latest_point: Optional[TradingPoint] = None


def detect_purchase_points(
    strokes: list[Stroke],
    segments: list[Segment],
    centers: list[Center],
    divergences: list[Divergence],
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> list[TradingPoint]:
    """
    检测所有买点（一买、二买、三买）。
    
    Args:
        strokes: 笔列表
        segments: 线段列表
        centers: 中枢列表
        divergences: 背驰列表
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        
    Returns:
        买点列表
    """
    points = []
    
    if len(strokes) < 3:
        return points

    # ── 一买：底背驰后，第一个上升笔的终点 ──────────────────
    for div in divergences:
        if div.divergence_type == DivergenceType.BULLISH:
            # 找到背驰后第一个上升笔
            for stroke in strokes:
                if stroke.direction == StrokeDirection.UP and stroke.end_idx > div.price_extremum_idx:
                    points.append(TradingPoint(
                        point_type=TradingPointType.PURCHASE_1,
                        price=stroke.end_price,
                        index=stroke.end_idx,
                        confidence=min(0.9, 0.6 + div.severity * 0.3),
                        stop_loss=div.price_extremum_value,
                        description=f"一买@{stroke.end_price:.2f}, 底背驰后, 止损{div.price_extremum_value:.2f}",
                    ))
                    break

    # ── 二买：回调不破一买低点 ──────────────────────────────
    purchase_1s = [p for p in points if p.point_type == TradingPointType.PURCHASE_1]
    if purchase_1s:
        p1 = purchase_1s[0]
        # 找一买之后的下降笔
        for i, stroke in enumerate(strokes):
            if stroke.direction == StrokeDirection.DOWN and stroke.end_idx > p1.index:
                # 回调低点
                pullback_low = min(stroke.start_price, stroke.end_price)
                if pullback_low > p1.price:
                    # 没破一买低点
                    # 找回调后的上升笔
                    for next_stroke in strokes[i + 1:]:
                        if next_stroke.direction == StrokeDirection.UP:
                            points.append(TradingPoint(
                                point_type=TradingPointType.PURCHASE_2,
                                price=pullback_low,
                                index=stroke.end_idx,
                                confidence=0.7,
                                related_center=centers[-1].index if centers else None,
                                stop_loss=p1.price * 0.98,
                                description=f"二买@{pullback_low:.2f}, 回调不破一买{p1.price:.2f}",
                            ))
                            break
                    break

    # ── 三买：离开中枢后，回调不破中枢上沿 ───────────────────
    if centers:
        latest_center = centers[-1]
        # 找离开中枢的笔
        for stroke in strokes:
            if stroke.end_idx > latest_center.end_idx:
                stroke_high = max(stroke.start_price, stroke.end_price)
                stroke_low = min(stroke.start_price, stroke.end_price)
                
                # 离开中枢后
                if stroke.direction == StrokeDirection.UP:
                    # 价格离开中枢上沿
                    if stroke_high > latest_center.zg:
                        # 找随后的回调
                        for next_stroke in strokes:
                            if next_stroke.direction == StrokeDirection.DOWN and next_stroke.end_idx > stroke.end_idx:
                                pullback = min(next_stroke.start_price, next_stroke.end_price)
                                # 回调不破中枢上沿 → 三买
                                if pullback > latest_center.zg:
                                    points.append(TradingPoint(
                                        point_type=TradingPointType.PURCHASE_3,
                                        price=pullback,
                                        index=next_stroke.end_idx,
                                        confidence=0.75,
                                        related_center=latest_center.index,
                                        description=f"三买@{pullback:.2f}, 回抽不破中枢{latest_center.zg:.2f}",
                                    ))
                                break
                        break

    return points


def detect_sell_points(
    strokes: list[Stroke],
    segments: list[Segment],
    centers: list[Center],
    divergences: list[Divergence],
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> list[TradingPoint]:
    """
    检测所有卖点（一卖、二卖、三卖）。
    
    Args:
        strokes: 笔列表
        segments: 线段列表
        centers: 中枢列表
        divergences: 背驰列表
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        
    Returns:
        卖点列表
    """
    points = []

    if len(strokes) < 3:
        return points

    # ── 一卖：顶背驰后，第一个下降笔的终点 ──────────────────
    for div in divergences:
        if div.divergence_type == DivergenceType.BEARISH:
            for stroke in strokes:
                if stroke.direction == StrokeDirection.DOWN and stroke.end_idx > div.price_extremum_idx:
                    points.append(TradingPoint(
                        point_type=TradingPointType.SELL_1,
                        price=stroke.end_price,
                        index=stroke.end_idx,
                        confidence=min(0.9, 0.6 + div.severity * 0.3),
                        stop_loss=div.price_extremum_value,
                        description=f"一卖@{stroke.end_price:.2f}, 顶背驰后, 止损{div.price_extremum_value:.2f}",
                    ))
                    break

    # ── 二卖：反弹不破一卖高点 ───────────────────────────────
    sell_1s = [p for p in points if p.point_type == TradingPointType.SELL_1]
    if sell_1s:
        s1 = sell_1s[0]
        for i, stroke in enumerate(strokes):
            if stroke.direction == StrokeDirection.UP and stroke.end_idx > s1.index:
                pullback_high = max(stroke.start_price, stroke.end_price)
                if pullback_high < s1.price:
                    for next_stroke in strokes[i + 1:]:
                        if next_stroke.direction == StrokeDirection.DOWN:
                            points.append(TradingPoint(
                                point_type=TradingPointType.SELL_2,
                                price=pullback_high,
                                index=stroke.end_idx,
                                confidence=0.7,
                                related_center=centers[-1].index if centers else None,
                                description=f"二卖@{pullback_high:.2f}, 反弹不破一卖{s1.price:.2f}",
                            ))
                            break
                    break

    # ── 三卖：离开中枢后，反弹不破中枢下沿 ───────────────────
    if centers:
        latest_center = centers[-1]
        for stroke in strokes:
            if stroke.end_idx > latest_center.end_idx:
                if stroke.direction == StrokeDirection.DOWN:
                    stroke_low = min(stroke.start_price, stroke.end_price)
                    if stroke_low < latest_center.zd:
                        for next_stroke in strokes:
                            if next_stroke.direction == StrokeDirection.UP and next_stroke.end_idx > stroke.end_idx:
                                rebound = max(next_stroke.start_price, next_stroke.end_price)
                                if rebound < latest_center.zd:
                                    points.append(TradingPoint(
                                        point_type=TradingPointType.SELL_3,
                                        price=rebound,
                                        index=next_stroke.end_idx,
                                        confidence=0.75,
                                        related_center=latest_center.index,
                                        description=f"三卖@{rebound:.2f}, 反弹不破中枢{latest_center.zd:.2f}",
                                    ))
                                break
                        break

    return points


def check_structure_invalidation(
    strokes: list[Stroke],
    divergences: list[Divergence],
    highs: np.ndarray,
    lows: np.ndarray,
) -> tuple[bool, Optional[str]]:
    """
    检测结构是否失效。
    
    结构失效条件:
    - 下跌走势中，价格创出新低但没有背驰 → 空头延续
    - 上涨走势中，价格创出新低但没有背驰 → 多头延续
    
    Returns:
        (is_invalid, reason)
    """
    if len(strokes) < 2:
        return False, None

    last_stroke = strokes[-1]
    
    # 如果最近一笔是下降笔，检查是否创出新低
    if last_stroke.direction == StrokeDirection.DOWN:
        # 找前一个下降笔
        prev_down = None
        for s in reversed(strokes[:-1]):
            if s.direction == StrokeDirection.DOWN:
                prev_down = s
                break
        
        if prev_down:
            # 当前下降笔创新低
            if last_stroke.end_price < prev_down.end_price:
                # 检查是否有底背驰伴随
                has_div = any(
                    d.divergence_type == DivergenceType.BULLISH and
                    d.price_extremum_idx >= last_stroke.end_idx
                    for d in divergences
                )
                if not has_div:
                    return True, "下跌创新低但无背驰，空头结构延续"

    # 如果最近一笔是上升笔，检查是否创出新高
    elif last_stroke.direction == StrokeDirection.UP:
        prev_up = None
        for s in reversed(strokes[:-1]):
            if s.direction == StrokeDirection.UP:
                prev_up = s
                break

        if prev_up:
            if last_stroke.end_price > prev_up.end_price:
                has_div = any(
                    d.divergence_type == DivergenceType.BEARISH and
                    d.price_extremum_idx >= last_stroke.end_idx
                    for d in divergences
                )
                if not has_div:
                    return True, "上涨创新高但无背驰，多头结构延续"

    return False, None


def get_latest_trading_point(
    points: list[TradingPoint],
) -> Optional[TradingPoint]:
    """获取最新的买卖点."""
    if not points:
        return None
    return max(points, key=lambda p: p.index)


def direction_from_point(point: Optional[TradingPoint]) -> str:
    """从买卖点类型判断方向."""
    if point is None:
        return "flat"
    
    purchase_types = {
        TradingPointType.PURCHASE_1,
        TradingPointType.PURCHASE_2,
        TradingPointType.PURCHASE_3,
    }
    sell_types = {
        TradingPointType.SELL_1,
        TradingPointType.SELL_2,
        TradingPointType.SELL_3,
    }

    if point.point_type in purchase_types:
        return "long"
    elif point.point_type in sell_types:
        return "short"
    else:
        return "flat"
