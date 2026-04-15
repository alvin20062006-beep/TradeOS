"""
资金流向分析模块
================

分析资金流入/流出压力。

⚠️ Proxy 版本: 从 OHLCV bars 估算
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass


@dataclass
class MoneyFlow:
    """资金流向指标."""
    net_flow: float            # 净流入（正=流入，负=流出）
    flow_ratio: float          # 流入/流出比
    money_flow_index: float    # MFI 0-100
    accumulation: str          # "accumulation" | "distribution" | "neutral"
    
    def __repr__(self):
        return f"MoneyFlow(net={self.net_flow:.0f}, mfi={self.money_flow_index:.1f})"


def calc_money_flow(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 14,
) -> MoneyFlow:
    """
    计算资金流向指标.
    
    Args:
        highs, lows, closes, volumes: OHLCV 数据
        lookback: MFI 计算窗口
        
    Returns:
        MoneyFlow
    """
    n = len(closes)
    if n < lookback:
        return MoneyFlow(
            net_flow=0.0,
            flow_ratio=1.0,
            money_flow_index=50.0,
            accumulation="neutral",
        )

    # 典型价格
    typical_price = (highs + lows + closes) / 3.0
    
    # 资金流 = 典型价格 × 成交量
    money_flow = typical_price * volumes
    
    # 正/负资金流
    positive_flow = []
    negative_flow = []
    
    for i in range(1, n):
        if typical_price[i] > typical_price[i - 1]:
            positive_flow.append(money_flow[i])
            negative_flow.append(0.0)
        elif typical_price[i] < typical_price[i - 1]:
            positive_flow.append(0.0)
            negative_flow.append(money_flow[i])
        else:
            positive_flow.append(0.0)
            negative_flow.append(0.0)
    
    # 最近 lookback 根
    pos_sum = sum(positive_flow[-lookback:]) if len(positive_flow) >= lookback else sum(positive_flow)
    neg_sum = sum(negative_flow[-lookback:]) if len(negative_flow) >= lookback else sum(negative_flow)
    
    # MFI
    if pos_sum + neg_sum > 0:
        mfi = 100.0 * pos_sum / (pos_sum + neg_sum)
    else:
        mfi = 50.0
    
    # 净流入
    net_flow = pos_sum - neg_sum
    
    # 流入/流出比
    flow_ratio = pos_sum / neg_sum if neg_sum > 0 else float('inf') if pos_sum > 0 else 1.0
    flow_ratio = min(10.0, flow_ratio)
    
    # 累积/派发判断
    if mfi > 70:
        accumulation = "accumulation"
    elif mfi < 30:
        accumulation = "distribution"
    else:
        accumulation = "neutral"
    
    return MoneyFlow(
        net_flow=round(net_flow, 2),
        flow_ratio=round(flow_ratio, 3),
        money_flow_index=round(mfi, 1),
        accumulation=accumulation,
    )


def calc_vwap_money_flow(
    closes: np.ndarray,
    volumes: np.ndarray,
    vwap: float,
) -> dict:
    """
    基于 VWAP 的资金流向.
    
    Returns:
        {"above_vwap_volume", "below_vwap_volume", "vwap_bias"}
    """
    if vwap <= 0 or len(closes) == 0:
        return {
            "above_vwap_volume": 0.0,
            "below_vwap_volume": 0.0,
            "vwap_bias": 0.0,
        }
    
    above_vol = 0.0
    below_vol = 0.0
    
    for i, (c, v) in enumerate(zip(closes, volumes)):
        if c > vwap:
            above_vol += v
        else:
            below_vol += v
    
    total = above_vol + below_vol
    bias = (above_vol - below_vol) / total if total > 0 else 0.0
    
    return {
        "above_vwap_volume": round(above_vol, 2),
        "below_vwap_volume": round(below_vol, 2),
        "vwap_bias": round(bias, 4),
    }
