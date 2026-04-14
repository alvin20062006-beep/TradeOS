"""
大单检测与成交量集中度
======================

检测大单（鲸鱼订单）并计算成交量集中度。

大单定义: 成交量 > 平均成交量 × large_multiplier
集中度: 大单成交量 / 总成交量
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.schemas import TradePrint, Side


@dataclass
class LargeTradeMetrics:
    """大单指标."""
    large_trade_count: int       # 大单笔数
    large_trade_volume: float    # 大单总量
    total_volume: float          # 总成交量
    concentration_ratio: float   # 集中度 (大单量/总量) 0-1
    avg_trade_size: float        # 平均单笔量
    large_multiplier: float      # 使用的大单倍数
    
    def __repr__(self):
        return (f"LargeTradeMetrics(count={self.large_trade_count}, "
                f"conc={self.concentration_ratio:.3f})")


def detect_large_trades(
    trades: list[TradePrint],
    large_multiplier: float = 3.0,
) -> LargeTradeMetrics:
    """
    检测大单并计算集中度.
    
    Args:
        trades: TradePrint 列表
        large_multiplier: 大单倍数（默认3倍平均量）
        
    Returns:
        LargeTradeMetrics
    """
    if not trades:
        return LargeTradeMetrics(
            large_trade_count=0, large_trade_volume=0.0,
            total_volume=0.0, concentration_ratio=0.0,
            avg_trade_size=0.0, large_multiplier=large_multiplier,
        )

    sizes = [t.size for t in trades]
    total_volume = sum(sizes)
    avg_size = total_volume / len(sizes) if sizes else 0.0
    threshold = avg_size * large_multiplier

    large_trades = [t for t in trades if t.size >= threshold]
    large_volume = sum(t.size for t in large_trades)

    concentration = large_volume / total_volume if total_volume > 0 else 0.0

    return LargeTradeMetrics(
        large_trade_count=len(large_trades),
        large_trade_volume=round(large_volume, 2),
        total_volume=round(total_volume, 2),
        concentration_ratio=round(concentration, 4),
        avg_trade_size=round(avg_size, 2),
        large_multiplier=large_multiplier,
    )


def large_trade_direction_bias(
    trades: list[TradePrint],
    large_multiplier: float = 3.0,
) -> dict:
    """
    大单方向偏差。
    
    Returns:
        {"buy_large_count", "sell_large_count", "buy_large_volume", 
         "sell_large_volume", "direction_bias": -1~1}
    """
    if not trades:
        return {"buy_large_count": 0, "sell_large_count": 0,
                "buy_large_volume": 0.0, "sell_large_volume": 0.0,
                "direction_bias": 0.0}

    sizes = [t.size for t in trades]
    avg_size = sum(sizes) / len(sizes)
    threshold = avg_size * large_multiplier

    buy_count = 0
    sell_count = 0
    buy_vol = 0.0
    sell_vol = 0.0

    for t in trades:
        if t.size >= threshold:
            if t.side == Side.BUY or t.is_buy_side_taker is True:
                buy_count += 1
                buy_vol += t.size
            elif t.side == Side.SELL or t.is_buy_side_taker is False:
                sell_count += 1
                sell_vol += t.size

    large_total = buy_vol + sell_vol
    bias = (buy_vol - sell_vol) / large_total if large_total > 0 else 0.0

    return {
        "buy_large_count": buy_count,
        "sell_large_count": sell_count,
        "buy_large_volume": round(buy_vol, 2),
        "sell_large_volume": round(sell_vol, 2),
        "direction_bias": round(bias, 4),
    }
