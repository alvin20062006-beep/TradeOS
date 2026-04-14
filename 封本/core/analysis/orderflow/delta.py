"""
Delta / CVD 计算模块
====================

Delta = Buy Volume - Sell Volume
CVD = Cumulative Delta (running sum)

输入: TradePrint[]
输出: {delta, cum_delta, buy_volume, sell_volume, buy_count, sell_count, 
       aggressive_buy_ratio, aggressive_sell_ratio}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.schemas import TradePrint, Side


@dataclass
class DeltaMetrics:
    """Delta/CVD 指标."""
    delta: float                # 本轮 delta (buy - sell)
    cum_delta: float            # 累计 delta
    buy_volume: float           # 买入量
    sell_volume: float          # 卖出量
    buy_count: int              # 买入笔数
    sell_count: int             # 卖出笔数
    aggressive_buy_ratio: float # 主动买入占比 (0-1)
    aggressive_sell_ratio: float  # 主动卖出占比 (0-1)
    trade_count: int            # 总笔数
    
    def __repr__(self):
        return (f"DeltaMetrics(delta={self.delta:.0f}, cum={self.cum_delta:.0f}, "
                f"buy_ratio={self.aggressive_buy_ratio:.2f})")


def calc_delta(
    trades: list[TradePrint],
    prev_cum_delta: float = 0.0,
) -> DeltaMetrics:
    """
    计算 Delta/CVD 指标.
    
    Args:
        trades: TradePrint 列表
        prev_cum_delta: 上一轮的累计 delta
        
    Returns:
        DeltaMetrics
    """
    buy_volume = 0.0
    sell_volume = 0.0
    buy_count = 0
    sell_count = 0

    for trade in trades:
        # 判断主动方向
        if trade.side == Side.BUY or trade.is_buy_side_taker is True:
            buy_volume += trade.size
            buy_count += 1
        elif trade.side == Side.SELL or trade.is_buy_side_taker is False:
            sell_volume += trade.size
            sell_count += 1
        else:
            # 无法判断方向 → 按 50/50 分配
            buy_volume += trade.size * 0.5
            sell_volume += trade.size * 0.5
            buy_count += 1
            sell_count += 1

    total_volume = buy_volume + sell_volume
    total_count = buy_count + sell_count

    delta = buy_volume - sell_volume
    cum_delta = prev_cum_delta + delta

    aggressive_buy_ratio = buy_volume / total_volume if total_volume > 0 else 0.5
    aggressive_sell_ratio = sell_volume / total_volume if total_volume > 0 else 0.5

    return DeltaMetrics(
        delta=round(delta, 2),
        cum_delta=round(cum_delta, 2),
        buy_volume=round(buy_volume, 2),
        sell_volume=round(sell_volume, 2),
        buy_count=buy_count,
        sell_count=sell_count,
        aggressive_buy_ratio=round(aggressive_buy_ratio, 4),
        aggressive_sell_ratio=round(aggressive_sell_ratio, 4),
        trade_count=total_count,
    )


def cvd_series(trades: list[TradePrint]) -> list[float]:
    """
    生成 CVD 时间序列.
    
    Returns:
        [cum_delta_0, cum_delta_1, ...]
    """
    series = []
    running = 0.0
    for trade in trades:
        if trade.side == Side.BUY or trade.is_buy_side_taker is True:
            running += trade.size
        elif trade.side == Side.SELL or trade.is_buy_side_taker is False:
            running -= trade.size
        series.append(round(running, 2))
    return series
