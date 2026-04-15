"""
流动性状态分析模块
==================

分析市场整体流动性状态。

⚠️ Proxy 版本: 从波动性和成交量估算
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass


@dataclass
class LiquidityCondition:
    """流动性状态指标."""
    condition: str          # "abundant" | "normal" | "strained" | "crisis"
    score: float             # 0 (枯竭) ~ 1 (充裕)
    spread_proxy: float     # 流动性价差代理
    depth_proxy: float       # 流动性深度代理
    is_proxy: bool = True   # ⚠️ 始终为 True
    
    def __repr__(self):
        return f"LiquidityCondition(condition={self.condition}, score={self.score:.2f})"


def calc_liquidity_from_bars(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 20,
) -> LiquidityCondition:
    """
    从 OHLCV bars 估算流动性状态（Proxy 方法）.
    
    指标:
    - 波动性：低波动 → 流动性好
    - 成交量：正常 → 流动性好
    - 价格冲击：大幅下跌伴随量能 → 流动性紧张
    
    Args:
        highs, lows, closes, volumes: OHLCV 数据
        lookback: 回看窗口
        
    Returns:
        LiquidityCondition
    """
    n = len(closes)
    if n < lookback:
        return LiquidityCondition(
            condition="normal",
            score=0.5,
            spread_proxy=0.0,
            depth_proxy=0.0,
            is_proxy=True,
        )

    # 1. 波动性
    returns = np.diff(closes[-lookback:]) / closes[-lookback:-1]
    volatility = np.std(returns)
    
    # 年化波动性（假设252交易日）
    ann_vol = volatility * np.sqrt(252)

    # 2. 成交量趋势
    vol_mean = np.mean(volumes[-lookback:])
    vol_recent = np.mean(volumes[-5:]) if n >= 5 else np.mean(volumes)
    vol_ratio = vol_recent / vol_mean if vol_mean > 0 else 1.0

    # 3. 价格冲击检测（快速下跌 + 放量）
    recent_returns = returns[-5:]
    recent_vols = volumes[-4:]
    crash_signal = False
    for i in range(len(recent_returns)):
        if recent_returns[i] < -0.02 and i + 1 < len(recent_vols):
            # 大跌且次日放量
            if recent_vols[i] > vol_mean * 2:
                crash_signal = True

    # 4. 综合评分
    # 波动性：高波动 → 低流动性
    vol_score = 1.0 - min(1.0, ann_vol / 0.3)  # 30% 年化波动 = 满分

    # 成交量：正常 → 好，极端 → 差
    if 0.8 <= vol_ratio <= 1.5:
        vol_flow_score = 0.7
    elif vol_ratio < 0.5:
        vol_flow_score = 0.4  # 低量 → 流动性差
    elif vol_ratio > 3.0:
        vol_flow_score = 0.3  # 极端放量 → 市场紧张
    else:
        vol_flow_score = 0.5

    # 综合
    score = vol_score * 0.6 + vol_flow_score * 0.4
    
    # 崩溃信号 → 流动性危机
    if crash_signal:
        score = min(0.2, score)

    # 状态标签
    if score > 0.7:
        condition = "abundant"
    elif score > 0.45:
        condition = "normal"
    elif score > 0.25:
        condition = "strained"
    else:
        condition = "crisis"

    # 价差代理：波动性高 → 价差大
    spread_proxy = min(1.0, ann_vol / 0.2)
    
    # 深度代理：成交量大 → 深度好
    depth_proxy = min(1.0, vol_ratio / 2.0)

    return LiquidityCondition(
        condition=condition,
        score=round(score, 3),
        spread_proxy=round(spread_proxy, 3),
        depth_proxy=round(depth_proxy, 3),
        is_proxy=True,
    )
