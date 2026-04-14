"""
流动性扫荡检测模块 (Liquidity Sweep)
===================================

检测大单扫荡流动性（突破、扫损）。

扫荡特征:
- 价格快速移动突破关键价位
- 成交量急剧放大
- 可能触发止损（stop hunt）

⚠️ Proxy 版本: 从 OHLCV bars 检测快速突破
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class SweepMetrics:
    """扫荡指标."""
    sweep_detected: bool          # 是否检测到扫荡
    sweep_direction: str          # "up" | "down" | "none"
    sweep_magnitude: float        # 扫荡幅度（相对）
    sweep_volume: float           # 扫荡成交量
    sweep_price_start: float      # 扫荡起点价格
    sweep_price_end: float        # 扫荡终点价格
    confidence: float             # 置信度 0-1
    
    def __repr__(self):
        return (f"Sweep(detected={self.sweep_detected}, dir={self.sweep_direction}, "
                f"mag={self.sweep_magnitude:.3f})")


def detect_sweep_from_bars(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 5,
    price_move_threshold: float = 0.02,  # 2% 价格变动
    volume_spike_ratio: float = 2.0,
) -> SweepMetrics:
    """
    从 OHLCV bars 检测流动性扫荡.
    
    算法:
    1. 找最近 lookback 根内最大价格变动
    2. 检查成交量是否异常放大
    3. 判断方向
    
    Args:
        highs, lows, closes, volumes: OHLCV 数据
        lookback: 回看窗口
        price_move_threshold: 价格变动阈值（相对）
        volume_spike_ratio: 成交量放大倍数
        
    Returns:
        SweepMetrics
    """
    n = len(closes)
    if n < lookback:
        return SweepMetrics(
            sweep_detected=False, sweep_direction="none",
            sweep_magnitude=0.0, sweep_volume=0.0,
            sweep_price_start=0.0, sweep_price_end=0.0, confidence=0.0,
        )

    # 最近 lookback 根
    h = highs[-lookback:]
    l = lows[-lookback:]
    c = closes[-lookback:]
    v = volumes[-lookback:]

    # 找最大涨幅和最大跌幅
    max_high = np.max(h)
    min_low = np.min(l)
    start_price = c[0]

    up_move = (max_high - start_price) / start_price if start_price > 0 else 0.0
    down_move = (start_price - min_low) / start_price if start_price > 0 else 0.0

    # 成交量
    avg_vol = np.mean(volumes)
    max_vol = np.max(v)
    vol_spike = max_vol / avg_vol if avg_vol > 0 else 1.0

    # 判断
    sweep_detected = False
    sweep_direction = "none"
    sweep_magnitude = 0.0
    confidence = 0.0

    if up_move >= price_move_threshold and vol_spike >= volume_spike_ratio:
        sweep_detected = True
        sweep_direction = "up"
        sweep_magnitude = up_move
        confidence = min(1.0, (up_move / price_move_threshold) * (vol_spike / volume_spike_ratio) * 0.5)
    elif down_move >= price_move_threshold and vol_spike >= volume_spike_ratio:
        sweep_detected = True
        sweep_direction = "down"
        sweep_magnitude = down_move
        confidence = min(1.0, (down_move / price_move_threshold) * (vol_spike / volume_spike_ratio) * 0.5)

    if sweep_detected:
        if sweep_direction == "up":
            end_price = max_high
        else:
            end_price = min_low
    else:
        end_price = c[-1]

    return SweepMetrics(
        sweep_detected=sweep_detected,
        sweep_direction=sweep_direction,
        sweep_magnitude=round(sweep_magnitude, 4),
        sweep_volume=round(max_vol, 2),
        sweep_price_start=round(start_price, 4),
        sweep_price_end=round(end_price, 4),
        confidence=round(confidence, 3),
    )


def detect_stop_hunt_zones(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 20,
    spike_threshold: float = 3.0,
) -> list[tuple[float, float]]:
    """
    检测潜在止损猎杀区域.
    
    算法: 找价格快速突破后快速回撤的区域
    
    Args:
        highs, lows, closes, volumes: OHLCV 数据
        lookback: 回看窗口
        spike_threshold: 成交量放大倍数
        
    Returns:
        [(low, high), ...] 潜在止损区域列表
    """
    n = len(closes)
    if n < lookback:
        return []

    zones = []
    avg_vol = np.mean(volumes[-lookback:])

    for i in range(-lookback, -1):
        if volumes[i] > avg_vol * spike_threshold:
            # 成交量异常
            # 检查是否快速回撤
            if i + 2 < 0:
                # 突破后2根内回撤
                if closes[i + 2] < highs[i] and closes[i + 2] > lows[i]:
                    # 回撤到突破区间内
                    zones.append((float(lows[i]), float(highs[i])))

    return zones
