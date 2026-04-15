"""
Volatility Targeting Position Sizing
==================================

qty = portfolio_equity × target_annual_vol / (price × realized_vol_20d)

基准算法（默认优先级最高）。
"""

from __future__ import annotations

from core.risk.calculators.base import PositionCalculator


class VolatilityTargetingCalculator(PositionCalculator):
    """
    目标组合波动率 sizing。

    公式：qty = (portfolio_equity × target_annual_vol) / (price × realized_vol)

    示例：
      portfolio_equity = $100,000
      target_annual_vol = 15%
      price = $200
      realized_vol = 25%

      qty = ($100,000 × 0.15) / ($200 × 0.25) = 300 shares
    """

    @property
    def method_name(self) -> str:
        return "volatility_targeting"

    def _compute(
        self,
        portfolio_equity: float,
        direction_confidence: float,
        direction_sign: int,
        market_context,
        target_annual_vol: float = 0.15,
        **kwargs,
    ) -> dict:
        price = market_context.current_price
        realized_vol = market_context.realized_vol_20d

        if price <= 0:
            return self._zero("price <= 0")
        if realized_vol <= 0:
            return self._zero(f"realized_vol={realized_vol} <= 0, 无法计算")

        dollar_vol_per_share = price * realized_vol
        qty = (portfolio_equity * target_annual_vol) / dollar_vol_per_share

        target_vol_str = f"{target_annual_vol * 100:.0f}%"
        realized_str = f"{realized_vol * 100:.0f}%"

        return {
            "qty": max(qty, 0.0),
            "confidence": min(direction_confidence + 0.1, 1.0),
            "rationale": (
                f"VolTargeting: "
                f"${portfolio_equity:,.0f} × {target_vol_str} "
                f"/ (${price} × {realized_str}) = {qty:.0f} shares"
            ),
            "method": self.method_name,
        }

    def _zero(self, reason: str) -> dict:
        return {"qty": 0.0, "confidence": 0.0, "rationale": reason, "method": self.method_name}
