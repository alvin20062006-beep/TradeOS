"""
执行质量预测模块 (Execution Quality)
===================================

预测执行质量、滑点估算。

基于订单簿深度和近期成交估算执行成本。
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional

from core.schemas import OrderBookSnapshot, ExecutionQuality


@dataclass
class ExecutionMetrics:
    """执行质量指标."""
    expected_slippage: float      # 预期滑点 (bps)
    execution_condition: ExecutionQuality
    available_liquidity: float    # 可用流动性
    market_impact: float          # 预估市场冲击
    
    def __repr__(self):
        return (f"Execution(slippage={self.expected_slippage:.1f}bps, "
                f"quality={self.execution_condition.value})")


def estimate_execution_quality(
    snapshot: Optional[OrderBookSnapshot],
    order_size: float,
    side: str = "buy",
) -> ExecutionMetrics:
    """
    估算执行质量.
    
    Args:
        snapshot: 订单簿快照（可选）
        order_size: 订单大小
        side: "buy" | "sell"
        
    Returns:
        ExecutionMetrics
    """
    if snapshot is None or not snapshot.bids or not snapshot.asks:
        return ExecutionMetrics(
            expected_slippage=50.0,  # 默认 50 bps
            execution_condition=ExecutionQuality.FAIR,
            available_liquidity=0.0,
            market_impact=0.0,
        )

    bids = snapshot.bids
    asks = snapshot.asks

    if side == "buy":
        # 买入需要消耗 ask 侧流动性
        levels = asks
    else:
        # 卖出需要消耗 bid 侧流动性
        levels = bids

    # 计算需要穿透的档位
    filled = 0.0
    total_cost = 0.0
    levels_used = 0

    for price, size in levels:
        fill_at_level = min(size, order_size - filled)
        total_cost += fill_at_level * price
        filled += fill_at_level
        levels_used += 1
        if filled >= order_size:
            break

    if filled == 0:
        return ExecutionMetrics(
            expected_slippage=100.0,
            execution_condition=ExecutionQuality.POOR,
            available_liquidity=0.0,
            market_impact=0.0,
        )

    # 计算平均成交价
    avg_price = total_cost / filled
    best_price = levels[0][0] if levels else 0.0

    # 滑点 (bps)
    if best_price > 0:
        slippage_bps = abs(avg_price - best_price) / best_price * 10000
    else:
        slippage_bps = 0.0

    # 执行质量评级
    if slippage_bps < 5:
        quality = ExecutionQuality.EXCELLENT
    elif slippage_bps < 15:
        quality = ExecutionQuality.GOOD
    elif slippage_bps < 50:
        quality = ExecutionQuality.FAIR
    else:
        quality = ExecutionQuality.POOR

    # 可用流动性
    available_liquidity = sum(size for _, size in levels)

    # 市场冲击估算
    if available_liquidity > 0:
        market_impact = order_size / available_liquidity
    else:
        market_impact = 1.0

    return ExecutionMetrics(
        expected_slippage=round(slippage_bps, 1),
        execution_condition=quality,
        available_liquidity=round(available_liquidity, 2),
        market_impact=round(market_impact, 4),
    )


def estimate_slippage_from_bars(
    volumes: np.ndarray,
    avg_trade_size: float = 100.0,
) -> float:
    """
    从成交量估算滑点（Proxy 方法）.
    
    Proxy: 基于成交量和波动性估算
    """
    if len(volumes) == 0:
        return 10.0

    avg_vol = np.mean(volumes)
    std_vol = np.std(volumes) if len(volumes) > 1 else 0.0

    # 成交量波动越大，滑点越大
    vol_var = std_vol / avg_vol if avg_vol > 0 else 1.0
    base_slippage = 5.0 + vol_var * 10.0

    return round(base_slippage, 1)
