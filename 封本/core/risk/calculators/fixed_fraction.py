"""
Fixed Fraction Position Sizing
============================

qty = portfolio_equity × fixed_risk_pct / stop_distance

保守/回撤期使用。
"""

from __future__ import annotations

from core.risk.calculators.base import PositionCalculator


class FixedFractionCalculator(PositionCalculator):
    """
    固定风险比例 sizing。

    公式：qty = portfolio_equity × fixed_risk_pct / (price × stop_distance_pct)

    适用场景：保守/回撤期、无历史数据时的备用算法。
    """

    @property
    def method_name(self) -> str:
        return "fixed_fraction"

    def _compute(
        self,
        portfolio_equity: float,
        direction_confidence: float,
        direction_sign: int,
        market_context,
        stop_distance_pct: float = 0.02,
        **kwargs,
    ) -> dict:
        price = market_context.current_price
        atr = market_context.atr_14

        if price <= 0:
            return self._zero("price <= 0")

        # 止损距离 = ATR（若可用）× 乘数，否则固定百分比
        if atr > 0:
            stop_distance = atr / price  # ATR 转换为比例
        else:
            stop_distance = max(stop_distance_pct, 0.01)

        fixed_risk_pct = 0.01  # 默认 1% 组合风险

        dollar_risk = portfolio_equity * fixed_risk_pct
        dollar_risk_per_share = price * stop_distance

        if dollar_risk_per_share <= 0:
            return self._zero("dollar_risk_per_share <= 0")

        qty = dollar_risk / dollar_risk_per_share

        return {
            "qty": max(qty, 0.0),
            "confidence": 0.5,  # 固定分数置信度固定为 0.5
            "rationale": (
                f"FixedFraction: ${dollar_risk:.0f} risk / "
                f"${dollar_risk_per_share:.2f} per share = {qty:.0f} shares"
            ),
            "method": self.method_name,
        }

    def _zero(self, reason: str) -> dict:
        return {"qty": 0.0, "confidence": 0.0, "rationale": reason, "method": self.method_name}
