"""ParticipationRateFilter — 参与率上限约束。"""
from core.risk.filters.base import FilterResult, RiskFilter


class ParticipationRateFilter(RiskFilter):
    """
    参与率上限过滤器。

    目标数量对应的参与率 = qty × price / adv_20d
    参与率 > max → cap qty
    """

    name = "participation_rate"
    MAX_PARTICIPATION = {"low": 0.05, "medium": 0.10, "high": 0.20}

    def _filter(
        self,
        qty,
        direction_sign,
        market_context=None,
        urgency: str = "medium",
        **kwargs,
    ):
        if market_context is None:
            return FilterResult(True, qty, True, "pass", "no market_context")

        adv = market_context.avg_daily_volume_20d
        price = market_context.current_price
        if adv <= 0 or price <= 0:
            return FilterResult(True, qty, True, "pass", "no adv or price")

        notional = qty * price
        participation = notional / max(market_context.adv_20d_usd, notional)

        max_pr = self.MAX_PARTICIPATION.get(urgency, 0.10)
        if participation <= max_pr:
            return FilterResult(
                passed=True,
                adjusted_qty=qty,
                limit_check_passed=True,
                mode="pass",
                details=f"participation={participation:.2%} <= limit={max_pr:.2%}",
            )

        # Cap（调整不拒绝）：passed=True，mode="cap"
        max_notional = market_context.adv_20d_usd * max_pr
        capped_qty = max_notional / price

        return FilterResult(
            passed=True,
            adjusted_qty=capped_qty,
            limit_check_passed=True,
            mode="cap",
            details=f"participation cap: {qty:.0f} → {capped_qty:.0f} (rate={participation:.2%} > {max_pr:.2%})",
        )
