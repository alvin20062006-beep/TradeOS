"""
多空拥挤度与挤兑风险检测
========================

Crowding: 持仓集中度
Squeeze Risk: 轧空/轧多风险

⚠️ Proxy 版本: 从 OHLCV + 成交量估算
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class CrowdingMetrics:
    """拥挤度指标."""
    long_crowding: float      # 多头拥挤度 0-1
    short_crowding: float     # 空头拥挤度 0-1
    crowding_direction: str   # "long" | "short" | "neutral"
    squeeze_risk: str         # "none" | "short_squeeze" | "long_squeeze"
    squeeze_probability: float  # 0-1
    
    def __repr__(self):
        return f"Crowding(long={self.long_crowding:.2f}, short={self.short_crowding:.2f})"


def detect_crowding(
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 20,
) -> CrowdingMetrics:
    """
    检测多空拥挤度（Proxy 方法）.
    
    Proxy 逻辑:
    - 价格持续上涨 + 成交量放大 → 多头拥挤
    - 价格持续下跌 + 成交量放大 → 空头拥挤
    - 极端拥挤 → 挤兑风险
    
    Args:
        closes: 收盘价序列
        volumes: 成交量序列
        lookback: 回看窗口
        
    Returns:
        CrowdingMetrics
    """
    n = len(closes)
    if n < lookback:
        return CrowdingMetrics(
            long_crowding=0.5,
            short_crowding=0.5,
            crowding_direction="neutral",
            squeeze_risk="none",
            squeeze_probability=0.0,
        )

    # 1. 价格趋势
    returns = np.diff(closes[-lookback:]) / closes[-lookback:-1]
    positive_days = np.sum(returns > 0)
    negative_days = np.sum(returns < 0)
    total_return = (closes[-1] - closes[-lookback]) / closes[-lookback]

    # 2. 成交量
    avg_vol = np.mean(volumes[-lookback:])
    recent_vol = np.mean(volumes[-5:])
    vol_spike = recent_vol / avg_vol if avg_vol > 0 else 1.0

    # 3. 连续性（连续涨/跌天数）
    consecutive_up = 0
    consecutive_down = 0
    for r in reversed(returns):
        if r > 0:
            consecutive_up += 1
        else:
            break
    for r in reversed(returns):
        if r < 0:
            consecutive_down += 1
        else:
            break

    # 4. 拥挤度估算
    # 多头拥挤 = 价格持续涨 + 成交量放大
    long_crowd = min(1.0, (positive_days / lookback) * vol_spike * 0.5 + consecutive_up * 0.05)
    
    # 空头拥挤 = 价格持续跌 + 成交量放大
    short_crowd = min(1.0, (negative_days / lookback) * vol_spike * 0.5 + consecutive_down * 0.05)

    # 归一化
    total_crowd = long_crowd + short_crowd
    if total_crowd > 0:
        long_crowd = long_crowd / total_crowd
        short_crowd = short_crowd / total_crowd
    else:
        long_crowd = short_crowd = 0.5

    # 5. 方向
    if long_crowd > 0.65:
        direction = "long"
    elif short_crowd > 0.65:
        direction = "short"
    else:
        direction = "neutral"

    # 6. 挤兑风险
    # Short Squeeze: 空头过度拥挤 + 价格开始反弹
    # Long Squeeze: 多头过度拥挤 + 价格开始回调
    squeeze_risk = "none"
    squeeze_prob = 0.0

    if direction == "short" and total_return < -0.05:
        # 空头拥挤，但如果价格开始反弹 → 轧空风险
        if len(returns) >= 3 and returns[-1] > 0 and returns[-2] > 0:
            squeeze_risk = "short_squeeze"
            squeeze_prob = min(1.0, short_crowd * vol_spike * 0.5)
    elif direction == "long" and total_return > 0.05:
        # 多头拥挤，但如果价格开始回调 → 轧多风险
        if len(returns) >= 3 and returns[-1] < 0 and returns[-2] < 0:
            squeeze_risk = "long_squeeze"
            squeeze_prob = min(1.0, long_crowd * vol_spike * 0.5)

    return CrowdingMetrics(
        long_crowding=round(long_crowd, 3),
        short_crowding=round(short_crowd, 3),
        crowding_direction=direction,
        squeeze_risk=squeeze_risk,
        squeeze_probability=round(squeeze_prob, 3),
    )


def detect_extreme_positioning(
    closes: np.ndarray,
    volumes: np.ndarray,
    threshold: float = 0.8,
) -> Optional[str]:
    """
    检测极端持仓.
    
    Returns:
        "extreme_long" | "extreme_short" | None
    """
    metrics = detect_crowding(closes, volumes)
    
    if metrics.long_crowding > threshold:
        return "extreme_long"
    elif metrics.short_crowding > threshold:
        return "extreme_short"
    
    return None
