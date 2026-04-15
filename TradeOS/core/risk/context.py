"""
MarketContext — 市场环境数据聚合器
================================

从 Portfolio / Position / MarketBar 聚合市场数据。
所有 Phase 7 计算器和过滤器的共享输入。

使用 @dataclass：纯数据聚合，无 Pydantic 验证。
ge/gt 约束在 build_market_context 工厂函数中做运行时校验。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class MarketContext:
    """
    当前市场环境数据。

    由 RiskEngine 初始化时聚合，供所有计算器和过滤器使用。
    """
    symbol: str
    timestamp: datetime
    current_price: float

    # ── 流动性 ──────────────────────────────────
    avg_daily_volume_20d: float = 0.0
    adv_20d_usd: float = 0.0
    bid_ask_spread_bps: float = 0.0
    market_cap: float = 0.0
    order_book_depth_10pct: Optional[float] = None

    # ── 波动率 ──────────────────────────────────
    realized_vol_20d: float = 0.0
    implied_vol: Optional[float] = None
    atr_14: float = 0.0

    # ── 宏观 ────────────────────────────────────
    vix_level: Optional[float] = None

    # ── 辅助属性 ──────────────────────────────
    @property
    def adv_float(self) -> float:
        """ADV 参与率计算用的浮点数（兼容除法）。"""
        return max(self.avg_daily_volume_20d, 1.0)

    @property
    def is_high_volatility(self) -> bool:
        """年化波动率 > 30%。"""
        return self.realized_vol_20d > 0.30

    @property
    def is_low_liquidity(self) -> bool:
        """ADV < 100万 股。"""
        return self.avg_daily_volume_20d < 1_000_000

    @property
    def is_large_cap(self) -> bool:
        """市值 > 100亿美元。"""
        return self.market_cap > 10_000_000_000


def build_market_context(
    symbol: str,
    current_price: float,
    avg_daily_volume_20d: float = 0.0,
    realized_vol_20d: float = 0.0,
    atr_14: float = 0.0,
    bid_ask_spread_bps: float = 0.0,
    market_cap: float = 0.0,
    vix_level: Optional[float] = None,
    timestamp: Optional[datetime] = None,
) -> MarketContext:
    """
    工厂函数：从原始数据构建 MarketContext。

    运行时校验：
    - current_price > 0
    - realized_vol_20d ∈ [0, 1]
    - avg_daily_volume_20d ≥ 0
    """
    ts = timestamp or datetime.utcnow()
    price = max(current_price, 0.01)
    adv_usd = avg_daily_volume_20d * price
    vol = min(max(realized_vol_20d, 0.0), 5.0)  # 限制到 500%

    return MarketContext(
        symbol=symbol,
        timestamp=ts,
        current_price=price,
        avg_daily_volume_20d=max(avg_daily_volume_20d, 0.0),
        adv_20d_usd=max(adv_usd, 0.0),
        bid_ask_spread_bps=max(bid_ask_spread_bps, 0.0),
        market_cap=max(market_cap, 0.0),
        realized_vol_20d=vol,
        atr_14=max(atr_14, 0.0),
        vix_level=vix_level,
    )
