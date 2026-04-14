"""
情绪 Regime 检测模块
====================

判断市场情绪状态: risk-on / risk-off / neutral

⚠️ Proxy 版本: 从 OHLCV bars 估算
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import Enum


class SentimentRegime(str, Enum):
    """情绪 regime."""
    RISK_ON = "risk_on"      # 风险偏好上升
    RISK_OFF = "risk_off"   # 风险偏好下降
    NEUTRAL = "neutral"      # 中性


@dataclass
class RegimeMetrics:
    """Regime 指标."""
    regime: SentimentRegime
    confidence: float        # 0-1
    fear_greed_index: float  # 0-100 (0=极度恐惧, 100=极度贪婪)
    volatility_state: str    # "low" | "normal" | "high"
    trend_strength: float    # 0-1
    
    def __repr__(self):
        return f"Regime({self.regime.value}, fg={self.fear_greed_index:.0f})"


def detect_sentiment_regime(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 20,
) -> RegimeMetrics:
    """
    从 OHLCV 检测情绪 regime.
    
    指标:
    - 收益率趋势
    - 波动性
    - 成交量变化
    - 价格位置（在区间的高低）
    
    Args:
        closes, highs, lows, volumes: OHLCV 数据
        lookback: 回看窗口
        
    Returns:
        RegimeMetrics
    """
    n = len(closes)
    if n < lookback:
        return RegimeMetrics(
            regime=SentimentRegime.NEUTRAL,
            confidence=0.0,
            fear_greed_index=50.0,
            volatility_state="normal",
            trend_strength=0.0,
        )

    # 1. 收益率趋势
    returns = np.diff(closes[-lookback:]) / closes[-lookback:-1]
    total_return = (closes[-1] - closes[-lookback]) / closes[-lookback]
    
    # 2. 波动性
    daily_ranges = highs[-lookback:] - lows[-lookback:]
    avg_range = np.mean(daily_ranges)
    range_std = np.std(daily_ranges)
    recent_range = np.mean(daily_ranges[-5:])
    
    volatility_ratio = recent_range / avg_range if avg_range > 0 else 1.0
    if volatility_ratio > 1.5:
        vol_state = "high"
    elif volatility_ratio < 0.7:
        vol_state = "low"
    else:
        vol_state = "normal"
    
    # 3. 成交量变化
    vol_change = np.mean(volumes[-5:]) / np.mean(volumes[-lookback:-5]) if lookback > 5 else 1.0
    
    # 4. 价格位置
    period_high = np.max(highs[-lookback:])
    period_low = np.min(lows[-lookback:])
    price_position = (closes[-1] - period_low) / (period_high - period_low) if period_high > period_low else 0.5
    
    # 5. 趋势强度（线性回归斜率）
    x = np.arange(lookback)
    y = closes[-lookback:]
    slope = np.polyfit(x, y, 1)[0]
    trend_strength = min(1.0, abs(slope) / closes[-lookback] * lookback * 100) if closes[-lookback] > 0 else 0.0
    
    # 综合判断
    # Fear & Greed Index: 0-100
    fg_components = []
    
    # Momentum component (收益方向)
    momentum_score = 50 + total_return * 500  # 10% return → 100
    fg_components.append(np.clip(momentum_score, 0, 100))
    
    # Volatility component (反向)
    vol_score = 50 - (volatility_ratio - 1) * 30
    fg_components.append(np.clip(vol_score, 20, 80))
    
    # Volume component
    vol_score2 = 50 + (vol_change - 1) * 20
    fg_components.append(np.clip(vol_score2, 20, 80))
    
    # Price position component
    position_score = price_position * 100
    fg_components.append(position_score)
    
    fear_greed_index = np.mean(fg_components)
    
    # Regime 判断
    # Risk-On: 收益正 + 波动低 + 成交量放大 + 价格在上半区间
    if total_return > 0.02 and vol_state != "high" and vol_change > 1.1 and price_position > 0.6:
        regime = SentimentRegime.RISK_ON
        confidence = min(1.0, sum([total_return * 10, (vol_change - 1) * 2, price_position]))
    # Risk-Off: 收益负 + 波动高 + 成交量放大（恐慌抛售）
    elif total_return < -0.02 and (vol_state == "high" or vol_change > 1.3):
        regime = SentimentRegime.RISK_OFF
        confidence = min(1.0, sum([abs(total_return) * 10, (volatility_ratio - 1) * 2]))
    else:
        regime = SentimentRegime.NEUTRAL
        confidence = 0.3 + abs(trend_strength) * 0.3
    
    return RegimeMetrics(
        regime=regime,
        confidence=min(1.0, round(confidence, 3)),
        fear_greed_index=round(fear_greed_index, 1),
        volatility_state=vol_state,
        trend_strength=round(trend_strength, 3),
    )


def simple_fear_greed_index(
    closes: np.ndarray,
    baseline_period: int = 252,
) -> float:
    """
    简化的恐惧贪婪指数.
    
    基于价格相对历史的位置。
    """
    n = len(closes)
    period = min(baseline_period, n)
    
    if period < 10:
        return 50.0
    
    recent_close = closes[-1]
    period_high = np.max(closes[-period:])
    period_low = np.min(closes[-period:])
    
    if period_high == period_low:
        return 50.0
    
    # 价格在区间中的位置 0-100
    position = (recent_close - period_low) / (period_high - period_low) * 100
    
    return round(position, 1)