"""
VWAP 分析模块
=============

计算 VWAP 及其偏离度。

⚠️ Proxy 版本: 当数据层暂不提供逐笔数据时，可从 OHLCV bars 合成 VWAP proxy。
Proxy 方法: 用 (High+Low+Close)/3 作为典型价格，以 Volume 加权。
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VWAPMetrics:
    """VWAP 指标."""
    vwap: float                # VWAP 价格
    deviation: float           # 当前价偏离 VWAP 的百分比
    deviation_abs: float       # 绝对偏离
    current_price: float       # 当前价格
    volume_weighted_price: float  # 加权价格
    
    def __repr__(self):
        return f"VWAPMetrics(vwap={self.vwap:.2f}, dev={self.deviation:.4f})"


def calc_vwap_from_bars(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    current_price: Optional[float] = None,
) -> VWAPMetrics:
    """
    从 OHLCV bars 计算 VWAP (Proxy 方法).
    
    Proxy: 典型价格 = (H+L+C)/3, VWAP = Σ(typical_price × volume) / Σ(volume)
    
    Args:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        volumes: 成交量序列
        current_price: 当前价格（默认用最后一根bar的close）
        
    Returns:
        VWAPMetrics
    """
    n = len(closes)
    if n == 0:
        return VWAPMetrics(vwap=0.0, deviation=0.0, deviation_abs=0.0, 
                          current_price=0.0, volume_weighted_price=0.0)

    # 典型价格
    typical_prices = (highs + lows + closes) / 3.0

    # VWAP = Σ(tp × vol) / Σ(vol)
    total_tp_vol = np.sum(typical_prices * volumes)
    total_vol = np.sum(volumes)

    if total_vol == 0:
        return VWAPMetrics(vwap=0.0, deviation=0.0, deviation_abs=0.0,
                          current_price=float(closes[-1]), volume_weighted_price=0.0)

    vwap = total_tp_vol / total_vol
    current = current_price if current_price is not None else float(closes[-1])

    # 偏离度
    if vwap > 0:
        deviation = (current - vwap) / vwap
        deviation_abs = abs(deviation)
    else:
        deviation = 0.0
        deviation_abs = 0.0

    return VWAPMetrics(
        vwap=round(vwap, 4),
        deviation=round(deviation, 6),
        deviation_abs=round(deviation_abs, 6),
        current_price=round(current, 4),
        volume_weighted_price=round(vwap, 4),
    )


def calc_vwap_from_trades(
    prices: list[float],
    sizes: list[float],
    current_price: Optional[float] = None,
) -> VWAPMetrics:
    """
    从逐笔成交数据计算 VWAP (精确方法).
    
    VWAP = Σ(price × size) / Σ(size)
    
    Args:
        prices: 成交价格列表
        sizes: 成交量列表
        current_price: 当前价格
        
    Returns:
        VWAPMetrics
    """
    if not prices or not sizes:
        return VWAPMetrics(vwap=0.0, deviation=0.0, deviation_abs=0.0,
                          current_price=0.0, volume_weighted_price=0.0)

    prices_arr = np.array(prices)
    sizes_arr = np.array(sizes)

    total_pv = np.sum(prices_arr * sizes_arr)
    total_size = np.sum(sizes_arr)

    if total_size == 0:
        return VWAPMetrics(vwap=0.0, deviation=0.0, deviation_abs=0.0,
                          current_price=float(prices[-1]), volume_weighted_price=0.0)

    vwap = total_pv / total_size
    current = current_price if current_price is not None else float(prices[-1])

    if vwap > 0:
        deviation = (current - vwap) / vwap
        deviation_abs = abs(deviation)
    else:
        deviation = 0.0
        deviation_abs = 0.0

    return VWAPMetrics(
        vwap=round(vwap, 4),
        deviation=round(deviation, 6),
        deviation_abs=round(deviation_abs, 6),
        current_price=round(current, 4),
        volume_weighted_price=round(vwap, 4),
    )
