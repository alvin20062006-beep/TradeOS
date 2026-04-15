"""SlippageLimitFilter — max_slippage_bps."""
from core.risk.filters.base import FilterResult, RiskFilter


class SlippageLimitFilter(RiskFilter):
    """
    滑点限额过滤器。

    若 estimated_slippage_bps > max_slippage_bps → veto
    """

    name = "max_slippage_bps"

    def _filter(
        self,
        qty,
        direction_sign,
        risk_limits=None,
        estimated_slippage_bps: float = 0.0,
        **kwargs,
    ):
        if risk_limits is None:
            return FilterResult(True, qty, True, "pass", "no risk_limits")

        max_slippage = risk_limits.max_slippage_bps
        if estimated_slippage_bps <= max_slippage:
            return FilterResult(
                passed=True,
                adjusted_qty=qty,
                limit_check_passed=True,
                mode="pass",
                details=f"slippage={estimated_slippage_bps:.1f}bps <= limit={max_slippage:.1f}bps",
            )

        return FilterResult(
            passed=False,
            adjusted_qty=0.0,
            limit_check_passed=False,
            mode="veto",
            details=f"slippage veto: est={estimated_slippage_bps:.1f}bps > limit={max_slippage:.1f}bps",
        )
