"""
Regime-Based Position Sizing
============================

qty = base_qty × regime_multiplier

以市场状态修饰仓位。
"""

from __future__ import annotations

from core.risk.calculators.base import PositionCalculator


class RegimeBasedCalculator(PositionCalculator):
    """
    市场状态修饰 sizing。

    公式：qty = base_qty × regime_multiplier

    市场状态 → 仓位乘数映射：
      trending_up    : 1.2  （趋势强，增加仓位）
      trending_down  : 0.8  （趋势弱，降低仓位）
      ranging       : 1.0  （震荡市，基准仓位）
      volatile      : 0.5  （高波动，大幅降低仓位）
      unknown       : 0.8  （未知，保守）
    """

    REGIME_MULTIPLIERS = {
        "trending_up": 1.2,
        "trending_down": 0.8,
        "ranging": 1.0,
        "volatile": 0.5,
        "unknown": 0.8,
    }

    @property
    def method_name(self) -> str:
        return "regime_based"

    def _compute(
        self,
        portfolio_equity: float,
        direction_confidence: float,
        direction_sign: int,
        market_context,
        *,
        regime_multiplier: Optional[float] = None,
        regime_name: str = "unknown",
        **kwargs,
    ) -> dict:
        price = market_context.current_price
        if price <= 0:
            return self._zero("price <= 0")

        # 若未传入 regime_multiplier，从名称查找
        if regime_multiplier is None:
            regime_multiplier = self.REGIME_MULTIPLIERS.get(regime_name, 0.8)

        # 基准 5% portfolio fraction（使用 context 中的 current_price）
        base_fraction = 0.05
        base_qty = (portfolio_equity * base_fraction) / price
        qty = base_qty * regime_multiplier

        return {
            "qty": max(qty, 0.0),
            "confidence": direction_confidence * regime_multiplier,
            "rationale": (
                f"RegimeBased: regime={regime_name}, "
                f"multiplier={regime_multiplier:.2f}, qty={qty:.0f} shares"
            ),
            "method": self.method_name,
        }

    def _zero(self, reason: str) -> dict:
        return {"qty": 0.0, "confidence": 0.0, "rationale": reason, "method": self.method_name}
