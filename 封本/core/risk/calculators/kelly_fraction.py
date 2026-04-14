"""
Kelly Criterion Position Sizing
==============================

f* = (b × p - q) / b
半 Kelly = f* / 2

需要历史胜率数据才启用（无数据时跳过）。
"""

from __future__ import annotations

from core.risk.calculators.base import PositionCalculator


class KellyFractionCalculator(PositionCalculator):
    """
    Kelly Criterion sizing（半 Kelly）。

    公式：f* = (b × p - q) / b  其中 b = avg_win/avg_loss, p = win_rate, q = 1-p
    半 Kelly = f* / 2

    适用场景：有足够历史交易数据时。
    无 kelly_* 参数时返回零数量（不强制使用 Kelly）。
    """

    @property
    def method_name(self) -> str:
        return "kelly"

    def _compute(
        self,
        portfolio_equity: float,
        direction_confidence: float,
        direction_sign: int,
        market_context,
        kelly_win_rate: float = None,
        kelly_avg_win: float = None,
        kelly_avg_loss: float = None,
        **kwargs,
    ) -> dict:
        # Kelly 需要三个参数全部提供
        if kelly_win_rate is None or kelly_avg_win is None or kelly_avg_loss is None:
            return self._zero("Kelly: 缺少历史数据（win_rate/avg_win/avg_loss）")

        price = market_context.current_price
        if price <= 0:
            return self._zero("price <= 0")

        if kelly_avg_loss <= 0:
            return self._zero("kelly_avg_loss <= 0")

        p = kelly_win_rate
        b = kelly_avg_win / kelly_avg_loss
        q = 1 - p

        kelly = (b * p - q) / b
        kelly_fraction = max(kelly, 0.0) / 2  # 半 Kelly

        qty = portfolio_equity * kelly_fraction / price

        return {
            "qty": max(qty, 0.0),
            "confidence": min(direction_confidence + 0.05, 1.0),
            "rationale": (
                f"Kelly: win_rate={p:.1%}, b={b:.2f}, "
                f"Kelly={kelly:.3f}, half-Kelly={kelly_fraction:.3f}, "
                f"qty={qty:.0f} shares"
            ),
            "method": self.method_name,
        }

    def _zero(self, reason: str) -> dict:
        return {"qty": 0.0, "confidence": 0.0, "rationale": reason, "method": self.method_name}
