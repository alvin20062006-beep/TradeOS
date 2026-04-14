"""
订单簿分析模块 (Book Analyzer)
==============================

分析订单簿失衡、买卖压力、spread 等。

输入: OrderBookSnapshot
输出: {imbalance, bid_pressure, ask_pressure, spread, mid_price, depth_ratio}
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional

from core.schemas import OrderBookSnapshot


@dataclass
class BookMetrics:
    """订单簿指标."""
    imbalance: float           # -1 (全卖) ~ 1 (全买)
    bid_pressure: float        # 买方压力 0-1
    ask_pressure: float        # 卖方压力 0-1
    spread: float              # 点差
    mid_price: float           # 中间价
    total_bid_depth: float     # 总买量
    total_ask_depth: float     # 总卖量
    depth_ratio: float         # bid/total 深度比
    top_bid_volume: float      # 买一量
    top_ask_volume: float      # 卖一量
    top_imbalance: float       # 买一卖一失衡
    
    def __repr__(self):
        return (f"BookMetrics(imb={self.imbalance:.3f}, spread={self.spread:.4f}, "
                f"mid={self.mid_price:.2f})")


def analyze_book(snapshot: OrderBookSnapshot) -> BookMetrics:
    """
    分析订单簿快照.
    
    Args:
        snapshot: OrderBookSnapshot
        
    Returns:
        BookMetrics
    """
    bids = snapshot.bids or []
    asks = snapshot.asks or []

    # 基本量
    total_bid = sum(size for _, size in bids)
    total_ask = sum(size for _, size in asks)
    total_depth = total_bid + total_ask

    # 失衡: (bid - ask) / (bid + ask)
    if total_depth > 0:
        imbalance = (total_bid - total_ask) / total_depth
    else:
        imbalance = 0.0

    # 买卖压力
    bid_pressure = total_bid / total_depth if total_depth > 0 else 0.5
    ask_pressure = total_ask / total_depth if total_depth > 0 else 0.5

    # spread
    best_bid = bids[0][0] if bids else 0.0
    best_ask = asks[0][0] if asks else 0.0
    spread = best_ask - best_bid if best_ask > 0 else 0.0
    mid_price = (best_bid + best_ask) / 2 if best_ask > 0 else 0.0

    # 深度比
    depth_ratio = total_bid / total_depth if total_depth > 0 else 0.5

    # 买一卖一
    top_bid_vol = bids[0][1] if bids else 0.0
    top_ask_vol = asks[0][1] if asks else 0.0
    top_total = top_bid_vol + top_ask_vol
    top_imbalance = (top_bid_vol - top_ask_vol) / top_total if top_total > 0 else 0.0

    return BookMetrics(
        imbalance=round(imbalance, 4),
        bid_pressure=round(bid_pressure, 4),
        ask_pressure=round(ask_pressure, 4),
        spread=round(spread, 6),
        mid_price=mid_price,
        total_bid_depth=total_bid,
        total_ask_depth=total_ask,
        depth_ratio=round(depth_ratio, 4),
        top_bid_volume=top_bid_vol,
        top_ask_volume=top_ask_vol,
        top_imbalance=round(top_imbalance, 4),
    )


def weighted_imbalance(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    levels: int = 5,
) -> float:
    """
    加权订单簿失衡（越靠近中间价权重越高）。
    
    Args:
        bids: [(price, size), ...]
        asks: [(price, size), ...]
        levels: 使用的前N档
        
    Returns:
        加权失衡 -1 ~ 1
    """
    n_bids = min(levels, len(bids))
    n_asks = min(levels, len(asks))

    if n_bids == 0 and n_asks == 0:
        return 0.0

    # 距离加权：越靠近中间价权重越高
    bid_weighted = 0.0
    for i in range(n_bids):
        weight = 1.0 / (1.0 + i)  # 第1档权重=1, 第2档=0.5, ...
        bid_weighted += bids[i][1] * weight

    ask_weighted = 0.0
    for i in range(n_asks):
        weight = 1.0 / (1.0 + i)
        ask_weighted += asks[i][1] * weight

    total = bid_weighted + ask_weighted
    if total == 0:
        return 0.0

    return round((bid_weighted - ask_weighted) / total, 4)
