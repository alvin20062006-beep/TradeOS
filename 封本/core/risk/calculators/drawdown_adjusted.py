"""
Drawdown-Adjusted Position Sizing
=================================

qty = base_qty × max(0, 1 - drawdown_ratio)

在当前回撤期降低仓位。
"""

from __future__ import annotations

from core.risk.calculators.base import PositionCalculator


class DrawdownAdjustedCalculator(PositionCalculator):
    """
    回撤调整 sizing。

    公式：qty = base_qty × max(0, 1 - drawdown_ratio)

    drawdown_ratio = current_drawdown / peak_equity（0-1）
    - drawdown_ratio = 0.0 → 无回撤，正常仓位
    - drawdown_ratio = 0.5 → 50% 回撤，仅剩 50% 仓位
    - drawdown_ratio >= 1.0 → 完全回撤，仓位 = 0
    """

    @property
    def method_name(self) -> str:
        return "drawdown_adjusted"

    def _compute(
        self,
        portfolio_equity: float,
        direction_confidence: float,
        direction_sign: int,
        market_context,
        drawdown_ratio: float = 0.0,
        **kwargs,
    ) -> dict:
        price = market_context.current_price
        if price <= 0:
            return self._zero("price <= 0")

        # Drawdown adjustment：以 1 - drawdown_ratio 为乘数
        adj_factor = max(0.0, 1.0 - drawdown_ratio)

        # base 5% portfolio fraction
        base_fraction = 0.05
        base_qty = (portfolio_equity * base_fraction) / price
        qty = base_qty * adj_factor

        return {
            "qty": max(qty, 0.0),
            "confidence": direction_confidence * adj_factor,
            "rationale": (
                f"DrawdownAdjusted: drawdown={drawdown_ratio:.1%}, "
                f"factor={adj_factor:.1%}, qty={qty:.0f} shares"
            ),
            "method": self.method_name,
        }

    def _zero(self, reason: str) -> dict:
        return {"qty": 0.0, "confidence": 0.0, "rationale": reason, "method": self.method_name}
