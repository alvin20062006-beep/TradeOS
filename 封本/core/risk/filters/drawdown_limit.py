"""DrawdownLimitFilter — max_drawdown_pct."""
from core.risk.filters.base import FilterResult, RiskFilter


class DrawdownLimitFilter(RiskFilter):
    """回撤限额过滤器。"""

    name = "max_drawdown_pct"

    def _filter(
        self,
        qty,
        direction_sign,
        risk_limits=None,
        current_drawdown_pct=0.0,
        **kwargs,
    ):
        if risk_limits is None:
            return FilterResult(True, qty, True, "pass", "no risk_limits")

        limit = risk_limits.max_drawdown_pct

        if current_drawdown_pct >= limit:
            return FilterResult(
                passed=False,
                adjusted_qty=0.0,
                limit_check_passed=False,
                mode="veto",
                details=f"drawdown {current_drawdown_pct:.2%} >= limit {limit:.2%}",
            )

        return FilterResult(
            passed=True,
            adjusted_qty=qty,
            limit_check_passed=True,
            mode="pass",
            details=f"drawdown {current_drawdown_pct:.2%} < limit {limit:.2%}",
        )
