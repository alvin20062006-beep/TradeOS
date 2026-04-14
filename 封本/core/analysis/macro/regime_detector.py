"""
宏观 Regime 检测模块
====================

检测宏观状态: risk-on / risk-off / stagflation / deflationary

⚠️ Proxy 版本: 从 OHLCV bars + 波动性估算
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import Enum


class MacroRegime(str, Enum):
    """宏观 regime."""
    RISK_ON = "risk_on"          # 风险偏好上升
    RISK_OFF = "risk_off"        # 风险偏好下降
    STAGFLATION = "stagflation"  # 滞胀（高通胀 + 低增长）
    DEFLATIONARY = "deflationary"  # 通缩
    NEUTRAL = "neutral"          # 中性


@dataclass
class MacroRegimeMetrics:
    """宏观 Regime 指标."""
    regime: MacroRegime
    confidence: float           # 0-1
    growth_outlook: str         # "expanding" | "contracting" | "stable"
    inflation_outlook: str      # "rising" | "falling" | "stable"
    
    def __repr__(self):
        return f"MacroRegime({self.regime.value}, conf={self.confidence:.2f})"


def detect_macro_regime_proxy(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 60,
) -> MacroRegimeMetrics:
    """
    从 OHLCV bars 估算宏观 regime（Proxy 方法）.
    
    指标:
    - 价格趋势（增长代理）
    - 波动性（不确定性）
    - 成交量变化（市场参与度）
    - 极端价格位置（区间分析）
    
    ⚠️ 这是极其粗糙的代理。真实宏观 regime 应结合：
    - GDP 增速
    - CPI/PCE 通胀数据
    - 央行政策立场
    - VIX/Gold 等宏观指标
    
    Args:
        closes, highs, lows, volumes: OHLCV 数据
        lookback: 回看窗口（默认60天≈3个月）
        
    Returns:
        MacroRegimeMetrics
    """
    n = len(closes)
    if n < lookback:
        return MacroRegimeMetrics(
            regime=MacroRegime.NEUTRAL,
            confidence=0.0,
            growth_outlook="stable",
            inflation_outlook="stable",
        )

    # 1. 收益率趋势（增长代理）
    returns = np.diff(closes[-lookback:]) / closes[-lookback:-1]
    total_return = (closes[-1] - closes[-lookback]) / closes[-lookback]
    avg_daily_return = np.mean(returns)

    # 2. 波动性
    volatility = np.std(returns)
    ann_vol = volatility * np.sqrt(252)

    # 3. 成交量
    vol_recent = np.mean(volumes[-10:]) if n >= 10 else np.mean(volumes)
    vol_old = np.mean(volumes[-lookback:-10]) if n >= lookback else np.mean(volumes[:-10])
    vol_change = vol_recent / vol_old if vol_old > 0 else 1.0

    # 4. 价格位置
    period_high = np.max(highs[-lookback:])
    period_low = np.min(lows[-lookback:])
    price_position = (closes[-1] - period_low) / (period_high - period_low) if period_high > period_low else 0.5

    # 5. 方向判断
    # 增长
    if total_return > 0.05:
        growth = "expanding"
    elif total_return < -0.05:
        growth = "contracting"
    else:
        growth = "stable"

    # 通胀（简化：高波动 + 上涨 = 通胀压力）
    if ann_vol > 0.2 and total_return > 0:
        inflation = "rising"
    elif ann_vol > 0.2 and total_return < 0:
        inflation = "stable"
    elif ann_vol < 0.1:
        inflation = "falling"
    else:
        inflation = "stable"

    # 6. Regime 判断
    # Risk-On: 增长 + 低波动 + 成交量正常
    if growth == "expanding" and ann_vol < 0.2 and vol_change < 1.5:
        regime = MacroRegime.RISK_ON
        confidence = min(1.0, 0.5 + total_return * 3)
    # Risk-Off: 收缩 + 高波动
    elif growth == "contracting" and ann_vol > 0.15:
        regime = MacroRegime.RISK_OFF
        confidence = min(1.0, 0.5 + abs(total_return) * 3)
    # 滞胀: 价格下跌 + 高波动（经济差 + 市场动荡）
    elif growth == "contracting" and ann_vol > 0.15:
        regime = MacroRegime.STAGFLATION
        confidence = 0.5
    # 通缩: 低波动 + 低成交量 + 区间低位
    elif ann_vol < 0.1 and vol_change < 0.8 and price_position < 0.3:
        regime = MacroRegime.DEFLATIONARY
        confidence = min(1.0, (1 - price_position) * 0.8)
    else:
        regime = MacroRegime.NEUTRAL
        confidence = 0.3

    return MacroRegimeMetrics(
        regime=regime,
        confidence=min(1.0, round(confidence, 3)),
        growth_outlook=growth,
        inflation_outlook=inflation,
    )


def detect_regime_from_macro_events(
    events: list,
    rate_pressure,
    inflation_shock,
    liquidity,
) -> MacroRegimeMetrics:
    """
    从真实宏观事件 + 指标检测 regime.
    
    Args:
        events: MacroEvent[] 列表
        rate_pressure: RatePressure
        inflation_shock: InflationShock
        liquidity: LiquidityCondition
        
    Returns:
        MacroRegimeMetrics
    """
    if not events:
        return MacroRegimeMetrics(
            regime=MacroRegime.NEUTRAL,
            confidence=0.0,
            growth_outlook="stable",
            inflation_outlook="stable",
        )

    # 评分
    risk_on_score = 0.5
    confidence = 0.5

    # 利率压力
    if rate_pressure.pressure_score > 0.6:
        risk_on_score -= 0.2  # 紧缩 → risk off
        confidence += 0.1
    elif rate_pressure.pressure_score < 0.4:
        risk_on_score += 0.2  # 宽松 → risk on
        confidence += 0.1

    # 通胀
    if inflation_shock.shock_score > 0.65:
        risk_on_score -= 0.1
        confidence += 0.1
    elif inflation_shock.shock_score < 0.35:
        risk_on_score += 0.1

    # 流动性
    if liquidity.condition in ["strained", "crisis"]:
        risk_on_score -= 0.2
        confidence += 0.1
    elif liquidity.condition == "abundant":
        risk_on_score += 0.1

    # Regime
    if risk_on_score > 0.65:
        regime = MacroRegime.RISK_ON
    elif risk_on_score < 0.35:
        regime = MacroRegime.RISK_OFF
    else:
        regime = MacroRegime.NEUTRAL

    return MacroRegimeMetrics(
        regime=regime,
        confidence=min(1.0, round(confidence, 3)),
        growth_outlook="stable",
        inflation_outlook="stable",
    )
