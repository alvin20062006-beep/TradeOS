"""
通胀冲击分析模块
================

分析通胀意外对市场的影响。

⚠️ Proxy 版本: 从 PCE/CPI proxy 数据（暂无），暂时占位
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InflationShock:
    """通胀冲击指标."""
    shock_score: float        # 0 (通缩) ~ 0.5 (中性) ~ 1 (高通胀)
    direction: str            # "hot" (过热) | "cold" (过冷) | "neutral"
    unexpected: bool          # 是否为意外冲击
    impact_on_equity: str    # "negative" | "positive" | "neutral"
    impact_on_bond: str      # "negative" | "positive" | "neutral"
    impact_on_commodity: str  # "negative" | "positive" | "neutral"
    
    def __repr__(self):
        return f"InflationShock(score={self.shock_score:.2f}, dir={self.direction})"


def calc_inflation_shock_proxy(
    volatility: float,
    trend: str = "neutral",
) -> InflationShock:
    """
    从波动性估算通胀冲击（Proxy 方法）.
    
    ⚠️ 占位实现：波动性升高可能是通胀预期升温的信号，
    但也可能由其他因素引起，应结合真实 CPI/PCE 数据使用。
    
    Args:
        volatility: 当前波动率（年化）
        trend: 价格趋势 "up" | "down" | "neutral"
        
    Returns:
        InflationShock
    """
    # 简化：用波动性映射
    # 高波动 + 上涨 → 通胀预期
    if volatility > 0.25:
        score = 0.75
        direction = "hot"
        unexpected = True
    elif volatility > 0.15:
        score = 0.6
        direction = "hot"
        unexpected = False
    elif volatility < 0.05:
        score = 0.25
        direction = "cold"
        unexpected = False
    else:
        score = 0.5
        direction = "neutral"
        unexpected = False

    # 资产影响
    if direction == "hot":
        equity = "negative"  # 高通胀侵蚀利润
        bond = "negative"    # 通胀侵蚀债券价值
        commodity = "positive"  # 硬资产保值
    elif direction == "cold":
        equity = "negative"
        bond = "positive"    # 低通胀/通缩 → 债券受益
        commodity = "negative"
    else:
        equity = "neutral"
        bond = "neutral"
        commodity = "neutral"

    return InflationShock(
        shock_score=round(score, 3),
        direction=direction,
        unexpected=unexpected,
        impact_on_equity=equity,
        impact_on_bond=bond,
        impact_on_commodity=commodity,
    )


def parse_macro_event_inflation(
    event_name: str,
    actual: float,
    consensus: float,
) -> InflationShock:
    """
    从宏观事件数据解析通胀冲击.
    
    Args:
        event_name: 事件名称
        actual: 实际值
        consensus: 预期值
        
    Returns:
        InflationShock
    """
    name_lower = event_name.lower()
    
    # CPI/PPI/PCE 事件
    is_cpi = any(k in name_lower for k in ["cpi", "ppi", "pce", "inflation", "通胀", "消费者价格"])
    if not is_cpi:
        return calc_inflation_shock_proxy(volatility=0.15)
    
    surprise = actual - consensus
    surprise_pct = surprise / consensus if consensus != 0 else 0.0
    
    # 意外程度
    if abs(surprise_pct) < 0.02:
        score = 0.5
        unexpected = False
    elif abs(surprise_pct) < 0.05:
        score = 0.6 if surprise > 0 else 0.4
        unexpected = True
    else:
        score = 0.8 if surprise > 0 else 0.2
        unexpected = True
    
    if score > 0.6:
        direction = "hot"
    elif score < 0.4:
        direction = "cold"
    else:
        direction = "neutral"
    
    # 资产影响
    if direction == "hot":
        equity = "negative"
        bond = "negative"
        commodity = "positive"
    elif direction == "cold":
        equity = "negative"
        bond = "positive"
        commodity = "negative"
    else:
        equity = "neutral"
        bond = "neutral"
        commodity = "neutral"
    
    return InflationShock(
        shock_score=round(score, 3),
        direction=direction,
        unexpected=unexpected,
        impact_on_equity=equity,
        impact_on_bond=bond,
        impact_on_commodity=commodity,
    )
