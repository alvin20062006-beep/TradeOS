"""
风险事件强度分析模块
====================

分析单个宏观事件对市场的冲击强度。

⚠️ Proxy 版本: 基于事件类型和已知影响分类
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EventShock:
    """事件冲击指标."""
    shock_score: float           # 0-1，冲击强度
    category: str               # 事件类别
    affected_assets: dict       # 受影响资产映射
    duration_hours: int         # 预计影响持续时长
    is_proxy: bool = True      # ⚠️ 始终为 True
    
    def __repr__(self):
        return f"EventShock(score={self.shock_score:.2f}, cat={self.category})"


# 已知高影响事件类型
HIGH_IMPACT_CATEGORIES = {
    "fomc", "fed", "ecb", "boe", "pce", "cpi", "nfp",
    "gdp", "pmi", "ism", "geopolitical", "crisis",
}

MEDIUM_IMPACT_CATEGORIES = {
    "retail", "housing", "consumer_confidence", "trade",
    "pmi_flash", "industrial_production", "capacity_utilization",
}

# 事件类别 → 资产影响映射
CATEGORY_IMPACT_MAP = {
    "fomc": {"equity": "negative", "bond": "positive", "fx": "positive"},
    "fed": {"equity": "negative", "bond": "positive", "fx": "positive"},
    "ecb": {"equity": "neutral", "bond": "neutral", "fx": "negative"},
    "boe": {"equity": "neutral", "bond": "neutral", "fx": "negative"},
    "pce": {"equity": "negative", "bond": "negative", "commodity": "positive"},
    "cpi": {"equity": "negative", "bond": "negative", "commodity": "positive"},
    "nfp": {"equity": "neutral", "bond": "neutral", "fx": "positive"},
    "gdp": {"equity": "positive", "bond": "negative", "fx": "positive"},
    "pmi": {"equity": "positive", "bond": "neutral", "fx": "neutral"},
    "geopolitical": {"equity": "negative", "bond": "positive", "commodity": "positive"},
    "crisis": {"equity": "negative", "bond": "positive", "fx": "positive"},
}


def calc_event_shock(
    event_name: str,
    country: str = "US",
    impact_level: str = "medium",
    actual: Optional[float] = None,
    consensus: Optional[float] = None,
) -> EventShock:
    """
    计算事件冲击强度.
    
    Args:
        event_name: 事件名称
        country: 国家代码
        impact_level: "high" | "medium" | "low"
        actual: 实际值（可选）
        consensus: 预期值（可选）
        
    Returns:
        EventShock
    """
    name_lower = event_name.lower()
    
    # 分类
    category = "unknown"
    for cat in HIGH_IMPACT_CATEGORIES:
        if cat in name_lower:
            category = cat
            break
    
    if category == "unknown":
        for cat in MEDIUM_IMPACT_CATEGORIES:
            if cat in name_lower:
                category = cat
                break
    
    # 基础分数
    base_scores = {"high": 0.8, "medium": 0.5, "low": 0.2}
    base_score = base_scores.get(impact_level.lower(), 0.5)
    
    # 惊喜加成（实际 vs 共识）
    surprise_bonus = 0.0
    if actual is not None and consensus is not None and consensus != 0:
        surprise = abs(actual - consensus) / abs(consensus)
        surprise_bonus = min(0.2, surprise * 2)
    
    shock_score = min(1.0, base_score + surprise_bonus)
    
    # 影响时长
    duration_map = {
        "fomc": 48, "fed": 48,
        "cpi": 24, "pce": 24, "nfp": 12,
        "gdp": 24, "pmi": 6,
        "geopolitical": 72, "crisis": 168,
    }
    duration_hours = duration_map.get(category, 6)
    
    # 资产影响
    affected = CATEGORY_IMPACT_MAP.get(category, {
        "equity": "neutral", "bond": "neutral", "commodity": "neutral", "fx": "neutral"
    })
    
    return EventShock(
        shock_score=round(shock_score, 3),
        category=category,
        affected_assets=affected,
        duration_hours=duration_hours,
        is_proxy=True,
    )


def calc_shock_from_returns(
    returns_1d: float,
    volatility: float,
    volume_spike: float = 1.0,
) -> EventShock:
    """
    从市场表现估算是否有隐含宏观冲击（Proxy 方法）.
    
    当没有明确宏观事件时，用市场异动来推断可能的宏观冲击。
    
    Returns:
        EventShock
    """
    # 极端下跌
    if returns_1d < -0.03 and volatility > 0.02:
        category = "geopolitical"
        shock_score = min(1.0, abs(returns_1d) * 20)
        affected = {"equity": "negative", "bond": "positive", "commodity": "negative"}
        duration = 48
    # 极端上涨
    elif returns_1d > 0.03 and volatility > 0.015:
        category = "fomc"  # 可能是宽松预期
        shock_score = min(0.8, returns_1d * 15)
        affected = {"equity": "positive", "bond": "negative", "commodity": "positive"}
        duration = 24
    # 正常
    else:
        category = "normal"
        shock_score = 0.1
        affected = {"equity": "neutral", "bond": "neutral", "commodity": "neutral"}
        duration = 0
    
    return EventShock(
        shock_score=round(shock_score, 3),
        category=category,
        affected_assets=affected,
        duration_hours=duration,
        is_proxy=True,
    )
