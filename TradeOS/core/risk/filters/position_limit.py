"""PositionLimitFilter — max_position_pct."""
from core.risk.filters.base import FilterResult, RiskFilter


class PositionLimitFilter(RiskFilter):
    """仓位比例上限过滤器。"""

    name = "max_position_pct"

    def _filter(
        self, qty, direction_sign, portfolio_equity=0.0, current_price=1.0, risk_limits=None, **kwargs
    ):
        if risk_limits is None:
            return FilterResult(True, qty, True, "pass", "no risk_limits")

        limit = risk_limits.max_position_pct
        limit_qty = (portfolio_equity * limit) / max(current_price, 0.01)

        if qty <= limit_qty:
            return FilterResult(
                passed=True,
                adjusted_qty=qty,
                limit_check_passed=True,
                mode="pass",
                details=f"qty={qty:.0f} <= limit={limit_qty:.0f} ({limit:.1%})",
            )

        # Cap（调整不拒绝）：passed=True，mode="cap"
        return FilterResult(
            passed=True,
            adjusted_qty=limit_qty,
            limit_check_passed=True,
            mode="cap",
            details=f"capped: {qty:.0f} → {limit_qty:.0f} (limit={limit:.1%})",
        )
