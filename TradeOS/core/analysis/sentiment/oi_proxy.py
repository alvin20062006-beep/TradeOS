"""
持仓量/资金费率/清算 Proxy 模块
================================

⚠️ PROXY 占位: 当前数据层暂不提供 OI/Funding/Liquidation 数据。
所有函数返回占位值，并在 metadata 中标注 proxy=True。

实际实现需要:
- Open Interest 数据（期货/永续合约）
- Funding Rate 数据（永续合约）
- 清算数据（交易所公开数据）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class OIProxy:
    """持仓量代理指标."""
    oi_estimate: float          # 估算持仓量（proxy）
    oi_change_pct: float        # 变化百分比
    funding_rate: float         # 资金费率（proxy）
    liquidation_risk: str       # "low" | "medium" | "high"
    is_proxy: bool = True       # ⚠️ 始终为 True
    
    def __repr__(self):
        return f"OIProxy(oi={self.oi_estimate:.0f}, funding={self.funding_rate:.4f})"


def proxy_oi_from_volume(
    recent_volume: float,
    avg_volume: float,
    price_change_pct: float = 0.0,
) -> OIProxy:
    """
    从成交量估算持仓量变化（Proxy 方法）.
    
    逻辑:
    - 成交量放大 + 价格上涨 → OI 增加（多头入场）
    - 成交量放大 + 价格下跌 → OI 增加（空头入场）
    - 成交量放大 + 价格震荡 → 换手（OI 不确定）
    
    ⚠️ 这是极其粗糙的代理，实际 OI 应从交易所获取。
    
    Args:
        recent_volume: 最近成交量
        avg_volume: 平均成交量
        price_change_pct: 价格变化百分比
        
    Returns:
        OIProxy
    """
    vol_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
    
    # 估算 OI 变化
    # 成交量放大 → 潜在 OI 增加
    oi_change = (vol_ratio - 1) * 100 * np.sign(price_change_pct) if vol_ratio > 1 else 0.0
    
    # 资金费率 proxy: 价格涨 + 成交量放大 → funding 正（多头付空头）
    # 简化: 用价格方向和成交量放大估算
    if vol_ratio > 1.5:
        funding = price_change_pct * 0.01  # 粗略映射
    else:
        funding = 0.0
    
    # 清算风险: 成交量极端放大 + 价格剧烈变动
    if vol_ratio > 3.0 and abs(price_change_pct) > 0.05:
        liq_risk = "high"
    elif vol_ratio > 2.0 and abs(price_change_pct) > 0.03:
        liq_risk = "medium"
    else:
        liq_risk = "low"
    
    return OIProxy(
        oi_estimate=recent_volume,  # 用成交量代理
        oi_change_pct=round(oi_change, 2),
        funding_rate=round(funding, 6),
        liquidation_risk=liq_risk,
        is_proxy=True,
    )


def get_liquidation_zones_proxy(
    current_price: float,
    price_range_pct: float = 0.05,
) -> list[tuple[float, float, str]]:
    """
    获取潜在清算区域（Proxy 方法）.
    
    ⚠️ 占位实现：返回固定间距区域。
    实际应从交易所清算数据获取。
    
    Returns:
        [(price_low, price_high, side), ...]
        side: "long_liquidation" | "short_liquidation"
    """
    # 占位：当前价格上下 5%
    upper_zone = (current_price * 1.03, current_price * 1.05, "short_liquidation")
    lower_zone = (current_price * 0.95, current_price * 0.97, "long_liquidation")
    
    return [lower_zone, upper_zone]


# 添加 numpy import
import numpy as np
