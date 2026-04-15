"""
Conviction-Weighted Position Sizing
==================================

qty = base_qty × arbitration_confidence

以仲裁层置信度为权重。
"""

from __future__ import annotations

from core.risk.calculators.base import PositionCalculator


class ConvictionWeightedCalculator(PositionCalculator):
    """
    仲裁置信度权重 sizing。

    公式：qty = base_qty × arbitration_confidence

    适用场景：参考值/低频决策/其他算法缺数据时。
    """

    @property
    def method_name(self) -> str:
        return "conviction_weighted"

    def _compute(
        self,
        portfolio_equity: float,
        direction_confidence: float,
        direction_sign: int,
        market_context,
        **kwargs,
    ) -> dict:
        price = market_context.current_price
        if price <= 0:
            return self._zero("price <= 0")

        # Conviction weighted：以置信度为权重，取组合的某个基准 fraction
        base_fraction = 0.05  # 基准 5% 组合
        base_qty = (portfolio_equity * base_fraction) / price
        qty = base_qty * direction_confidence

        return {
            "qty": max(qty, 0.0),
            "confidence": direction_confidence,
            "rationale": (
                f"ConvictionWeighted: "
                f"{base_fraction:.0%} portfolio × confidence={direction_confidence:.2f} "
                f"= {qty:.0f} shares"
            ),
            "method": self.method_name,
        }

    def _zero(self, reason: str) -> dict:
        return {"qty": 0.0, "confidence": 0.0, "rationale": reason, "method": self.method_name}
