"""LiquidityCapFilter — ADV 调整仓位上限。"""
from core.risk.filters.base import FilterResult, RiskFilter


class LiquidityCapFilter(RiskFilter):
    """
    流动性上限过滤器。

    公式：max_qty = adv_20d × max_participation（默认 20% ADV）
    qty > max_qty → cap to max_qty
    """

    name = "liquidity_cap"
    MAX_PARTICIPATION = 0.20  # 最大占总 ADV 比例

    def _filter(
        self,
        qty,
        direction_sign,
        market_context=None,
        risk_limits=None,
        **kwargs,
    ):
        if market_context is None:
            return FilterResult(True, qty, True, "pass", "no market_context")

        adv = market_context.avg_daily_volume_20d
        if adv <= 0:
            return FilterResult(True, qty, True, "pass", f"adv={adv}, no cap")

        max_participation = self.MAX_PARTICIPATION
        if risk_limits is not None:
            # 从 risk_limits 取最大单笔占总组合比例
            max_order_pct = getattr(risk_limits, "max_order_size_pct", 0.05)
            max_participation = min(max_order_pct * 10, self.MAX_PARTICIPATION)

        max_qty = adv * max_participation

        if qty <= max_qty:
            return FilterResult(
                passed=True,
                adjusted_qty=qty,
                limit_check_passed=True,
                mode="pass",
                details=f"qty={qty:.0f} <= adv_cap={max_qty:.0f} ({max_participation:.0%} ADV)",
            )

        # Cap（调整不拒绝）：passed=True，mode="cap"
        return FilterResult(
            passed=True,
            adjusted_qty=max_qty,
            limit_check_passed=True,
            mode="cap",
            details=f"liquidity cap: {qty:.0f} → {max_qty:.0f} ({max_participation:.0%} ADV)",
        )
