"""
吸收检测模块 (Absorption Detection)
===================================

检测大单吸收行为（冰山订单、被动吸收）。

吸收特征:
- 价格在某价位停滞
- 该价位出现大量成交
- 但价格未突破（被吸收）

⚠️ Proxy 版本: 当数据层暂不提供 Level 2 时，从 OHLCV bars 估算
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional

from core.schemas import TradePrint, Side


@dataclass
class AbsorptionMetrics:
    """吸收指标."""
    absorption_score: float       # 吸收强度 0-1
    absorbed_at_price: Optional[float]  # 吸收价位
    absorbed_volume: float        # 被吸收的量
    direction: str                # "buy_absorbed" | "sell_absorbed" | "none"
    
    def __repr__(self):
        return (f"Absorption(score={self.absorption_score:.2f}, "
                f"dir={self.direction}, vol={self.absorbed_volume:.0f})")


def detect_absorption(
    trades: list[TradePrint],
    price_tolerance: float = 0.001,  # 0.1% 价格容忍
    volume_threshold_ratio: float = 3.0,  # 成交量倍数
) -> AbsorptionMetrics:
    """
    从逐笔成交检测吸收.
    
    算法（简化）:
    1. 找到成交量最大的价位区间
    2. 检查该区间的买卖方向是否一面倒
    3. 如果是，则可能有吸收行为
    
    Args:
        trades: TradePrint 列表
        price_tolerance: 价位容忍度（相对）
        volume_threshold_ratio: 成交量阈值倍数
        
    Returns:
        AbsorptionMetrics
    """
    if not trades:
        return AbsorptionMetrics(
            absorption_score=0.0, absorbed_at_price=None,
            absorbed_volume=0.0, direction="none",
        )

    # 1. 找价格范围
    prices = [t.price for t in trades]
    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price

    if price_range == 0:
        # 所有交易在同一价位 → 可能是吸收
        total_vol = sum(t.size for t in trades)
        buy_vol = sum(t.size for t in trades if t.side == Side.BUY)
        sell_vol = total_vol - buy_vol

        if buy_vol > sell_vol:
            direction = "sell_absorbed"  # 卖单被吸收
        elif sell_vol > buy_vol:
            direction = "buy_absorbed"   # 买单被吸收
        else:
            direction = "none"

        return AbsorptionMetrics(
            absorption_score=min(1.0, total_vol / 10000),  # 简化
            absorbed_at_price=min_price,
            absorbed_volume=total_vol,
            direction=direction,
        )

    # 2. 分桶统计
    n_buckets = 10
    bucket_size = price_range / n_buckets
    bucket_volumes = [0.0] * n_buckets
    bucket_buy_volumes = [0.0] * n_buckets
    bucket_sell_volumes = [0.0] * n_buckets

    for t in trades:
        bucket_idx = int((t.price - min_price) / bucket_size)
        bucket_idx = min(bucket_idx, n_buckets - 1)
        bucket_volumes[bucket_idx] += t.size
        if t.side == Side.BUY:
            bucket_buy_volumes[bucket_idx] += t.size
        else:
            bucket_sell_volumes[bucket_idx] += t.size

    # 3. 找最大成交量 bucket
    max_vol_idx = bucket_volumes.index(max(bucket_volumes))
    max_vol = bucket_volumes[max_vol_idx]
    avg_vol = sum(bucket_volumes) / n_buckets

    # 4. 判断是否异常
    if max_vol < avg_vol * volume_threshold_ratio:
        return AbsorptionMetrics(
            absorption_score=0.0, absorbed_at_price=None,
            absorbed_volume=0.0, direction="none",
        )

    # 5. 判断方向
    buy_vol = bucket_buy_volumes[max_vol_idx]
    sell_vol = bucket_sell_volumes[max_vol_idx]
    total_in_bucket = buy_vol + sell_vol

    if total_in_bucket == 0:
        direction = "none"
    elif buy_vol > sell_vol * 1.5:
        direction = "sell_absorbed"
    elif sell_vol > buy_vol * 1.5:
        direction = "buy_absorbed"
    else:
        direction = "none"

    absorption_score = min(1.0, (max_vol - avg_vol) / (avg_vol + 1))
    absorbed_price = min_price + (max_vol_idx + 0.5) * bucket_size

    return AbsorptionMetrics(
        absorption_score=round(absorption_score, 3),
        absorbed_at_price=round(absorbed_price, 4),
        absorbed_volume=round(max_vol, 2),
        direction=direction,
    )


def detect_absorption_from_bars(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 10,
    volume_threshold_ratio: float = 2.0,
) -> AbsorptionMetrics:
    """
    从 OHLCV bars 检测吸收（Proxy 方法）.
    
    Proxy: 找价格波动小但成交量大的 bar
    
    Args:
        highs, lows, closes, volumes: OHLCV 数据
        lookback: 回看窗口
        volume_threshold_ratio: 成交量倍数
        
    Returns:
        AbsorptionMetrics
    """
    n = len(closes)
    if n < lookback:
        return AbsorptionMetrics(
            absorption_score=0.0, absorbed_at_price=None,
            absorbed_volume=0.0, direction="none",
        )

    # 最近 lookback 根
    h = highs[-lookback:]
    l = lows[-lookback:]
    c = closes[-lookback:]
    v = volumes[-lookback:]

    # 找波动小但量大的 bar
    ranges = h - l
    avg_range = np.mean(ranges)
    avg_vol = np.mean(v)

    # 波动 < 平均波动 / 2 且 成交量 > 平均成交量 * 2
    absorption_bars = []
    for i in range(lookback):
        if ranges[i] < avg_range * 0.5 and v[i] > avg_vol * volume_threshold_ratio:
            absorption_bars.append(i)

    if not absorption_bars:
        return AbsorptionMetrics(
            absorption_score=0.0, absorbed_at_price=None,
            absorbed_volume=0.0, direction="none",
        )

    # 取最近一根
    last_idx = absorption_bars[-1]
    absorbed_vol = v[last_idx]
    absorbed_price = c[last_idx]

    # 方向判断：收盘价在当日区间的位置
    bar_range = h[last_idx] - l[last_idx]
    if bar_range > 0:
        close_position = (c[last_idx] - l[last_idx]) / bar_range
        if close_position < 0.3:
            direction = "buy_absorbed"  # 收在低位 → 买单被吸收
        elif close_position > 0.7:
            direction = "sell_absorbed"  # 收在高位 → 卖单被吸收
        else:
            direction = "none"
    else:
        direction = "none"

    score = min(1.0, absorbed_vol / (avg_vol * volume_threshold_ratio))

    return AbsorptionMetrics(
        absorption_score=round(score, 3),
        absorbed_at_price=round(absorbed_price, 4),
        absorbed_volume=round(absorbed_vol, 2),
        direction=direction,
    )
