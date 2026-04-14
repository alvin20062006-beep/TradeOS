"""
成交量异动与拥挤度检测
======================

Volume Surprise: 成交量相对均值的偏离
Crowding: 成交量集中度/拥挤度

⚠️ Proxy 版本: 从 OHLCV bars 估算
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass


@dataclass
class VolumeMetrics:
    """成交量指标."""
    volume_surprise: float     # 成交量异动（相对均值的倍数）
    avg_volume: float         # 平均成交量
    recent_volume: float      # 最近成交量
    volume_trend: str         # "increasing" | "decreasing" | "stable"
    crowding_score: float     # 拥挤度 0-1
    
    def __repr__(self):
        return f"VolumeMetrics(surprise={self.volume_surprise:.2f}x, crowd={self.crowding_score:.2f})"


def calc_volume_surprise(
    volumes: np.ndarray,
    lookback: int = 20,
    recent_bars: int = 5,
) -> VolumeMetrics:
    """
    计算成交量异动.
    
    Args:
        volumes: 成交量序列
        lookback: 计算均值的窗口
        recent_bars: 计算最近成交量的bar数
        
    Returns:
        VolumeMetrics
    """
    n = len(volumes)
    if n < lookback:
        return VolumeMetrics(
            volume_surprise=1.0,
            avg_volume=float(np.mean(volumes)) if n > 0 else 0.0,
            recent_volume=float(volumes[-1]) if n > 0 else 0.0,
            volume_trend="stable",
            crowding_score=0.5,
        )

    # 历史均值（不含最近 recent_bars）
    if n > lookback + recent_bars:
        baseline = np.mean(volumes[-lookback - recent_bars:-recent_bars])
    else:
        baseline = np.mean(volumes[:-recent_bars]) if n > recent_bars else np.mean(volumes)

    recent_volume = np.mean(volumes[-recent_bars:])
    
    # 异动倍数
    surprise = recent_volume / baseline if baseline > 0 else 1.0
    
    # 趋势判断
    if n >= 10:
        early_avg = np.mean(volumes[-10:-5])
        late_avg = np.mean(volumes[-5:])
        if late_avg > early_avg * 1.2:
            trend = "increasing"
        elif late_avg < early_avg * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"
    
    # 拥挤度：成交量越高越拥挤
    # 用 relative volume + 波动iedades
    relative_volume = surprise
    if n >= lookback:
        vol_std = np.std(volumes[-lookback:])
        vol_mean = np.mean(volumes[-lookback:])
        cv = vol_std / vol_mean if vol_mean > 0 else 0.0
        # CV 越大 → 成交量波动大 → 拥挤度不确定 → 降低拥挤度
        # 简化: crowding = min(1, surprise/3) * (1 - cv/2)
        crowding = min(1.0, relative_volume / 3) * max(0.3, 1 - cv / 2)
    else:
        crowding = min(1.0, relative_volume / 3)

    return VolumeMetrics(
        volume_surprise=round(surprise, 2),
        avg_volume=round(baseline, 2),
        recent_volume=round(recent_volume, 2),
        volume_trend=trend,
        crowding_score=round(crowding, 3),
    )


def detect_extreme_crowding(
    volumes: np.ndarray,
    threshold_multiplier: float = 3.0,
) -> tuple[bool, str]:
    """
    检测极端拥挤.
    
    Returns:
        (is_extreme, description)
    """
    if len(volumes) < 20:
        return False, "insufficient_data"

    recent_vol = volumes[-1]
    avg_vol = np.mean(volumes[-20:])
    
    if recent_vol > avg_vol * threshold_multiplier:
        return True, f"volume_spike_{recent_vol / avg_vol:.1f}x"
    
    return False, "normal"