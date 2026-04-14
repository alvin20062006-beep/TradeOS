"""
利率压力分析模块
================

分析利率变化对市场的影响。

⚠️ Proxy 版本: 从债券收益率代理（若可用），或从价格波动性估算
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class RateDirection(str, Enum):
    """利率方向."""
    HIKING = "hiking"      # 加息
    CUTTING = "cutting"   # 降息
    ON_HOLD = "on_hold"   # 按兵不动


@dataclass
class RatePressure:
    """利率压力指标."""
    rate_direction: RateDirection
    pressure_score: float        # 0 (宽松) ~ 1 (紧缩)
    central_bank_stance: str      # "hawkish" | "dovish" | "neutral"
    rate_shock_probability: float  # 0-1，突发利率冲击概率
    
    def __repr__(self):
        return f"RatePressure(dir={self.rate_direction.value}, score={self.pressure_score:.2f})"


def calc_rate_pressure_proxy(
    returns_1d: float,
    volatility_20d: float,
    volume_trend: str = "stable",
) -> RatePressure:
    """
    从价格表现估算利率压力（Proxy 方法）.
    
    逻辑:
    - 股市下跌 + 波动性高 → 利率压力下降（宽松预期）
    - 债市下跌 → 利率压力上升
    - 成交量放大 → 市场不确定，可能提前定价利率变动
    
    ⚠️ 这是极其粗糙的代理，实际应从央行政策利率 + 债券收益率曲线获取。
    
    Args:
        returns_1d: 当日收益率
        volatility_20d: 20日波动率
        volume_trend: "increasing" | "decreasing" | "stable"
        
    Returns:
        RatePressure
    """
    # 收益率方向和幅度
    if returns_1d < -0.02:
        # 大跌 → 可能触发宽松预期
        pressure_score = max(0.0, 0.3 - abs(returns_1d) * 5)
    elif returns_1d > 0.02:
        # 大涨 → 紧缩压力
        pressure_score = min(1.0, 0.6 + returns_1d * 5)
    else:
        # 小幅波动 → 中性
        pressure_score = 0.5

    # 波动性加成
    if volatility_20d > 0.02:  # 高波动
        pressure_score = min(1.0, pressure_score + 0.1)
    elif volatility_20d < 0.005:  # 低波动
        pressure_score = max(0.0, pressure_score - 0.1)

    # 成交量放大 → 增加不确定性
    if volume_trend == "increasing":
        pressure_score = 0.4 + pressure_score * 0.6  # 往中性漂移

    # 央行立场
    if pressure_score > 0.65:
        stance = "hawkish"
    elif pressure_score < 0.35:
        stance = "dovish"
    else:
        stance = "neutral"

    # 利率冲击概率
    shock_prob = 0.0
    if volatility_20d > 0.03 and abs(returns_1d) > 0.02:
        shock_prob = min(1.0, volatility_20d * 20)

    # 方向
    if pressure_score > 0.6:
        direction = RateDirection.HIKING
    elif pressure_score < 0.4:
        direction = RateDirection.CUTTING
    else:
        direction = RateDirection.ON_HOLD

    return RatePressure(
        rate_direction=direction,
        pressure_score=round(pressure_score, 3),
        central_bank_stance=stance,
        rate_shock_probability=round(shock_prob, 3),
    )


def parse_macro_event_rate(
    event_name: str,
    impact: str = "medium",
) -> RatePressure:
    """
    从宏观事件文本解析利率影响.
    
    ⚠️ 简化占位实现：规则匹配关键词
    
    Args:
        event_name: 事件名称
        impact: "high" | "medium" | "low"
        
    Returns:
        RatePressure
    """
    name_lower = event_name.lower()
    
    # 加息相关
    if any(k in name_lower for k in ["rate hike", "tightening", "hawkish", "fed raise", "加息"]):
        direction = RateDirection.HIKING
        score = 0.8 if impact == "high" else 0.6
        stance = "hawkish"
    # 降息相关
    elif any(k in name_lower for k in ["rate cut", "easing", "dovish", "fed lower", "降息", "宽松"]):
        direction = RateDirection.CUTTING
        score = 0.2 if impact == "high" else 0.4
        stance = "dovish"
    # 暂停
    elif any(k in name_lower for k in ["pause", "on hold", "unchanged", "按兵不动"]):
        direction = RateDirection.ON_HOLD
        score = 0.5
        stance = "neutral"
    else:
        direction = RateDirection.ON_HOLD
        score = 0.5
        stance = "neutral"

    shock_prob = 0.8 if impact == "high" else 0.4 if impact == "medium" else 0.1

    return RatePressure(
        rate_direction=direction,
        pressure_score=score,
        central_bank_stance=stance,
        rate_shock_probability=shock_prob,
    )
