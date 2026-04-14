"""LossLimitFilter — max_loss_pct_per_trade / per_day."""
from core.risk.filters.base import FilterResult, RiskFilter


class LossLimitFilter(RiskFilter):
    """
    亏损限额过滤器。

    检查：
    1. 单笔亏损限额：qty × price × loss_pct ≤ 组合权益 × limit
    2. 日亏损限额：当日亏损占比 ≤ max_loss_pct_per_day
    """

    name = "loss_limit"

    def _filter(
        self,
        qty,
        direction_sign,
        portfolio_equity=1.0,
        current_price=1.0,
        risk_limits=None,
        daily_loss_pct=0.0,
        existing_position_qty=0.0,
        avg_entry_price=0.0,
        **kwargs,
    ):
        if risk_limits is None:
            return FilterResult(True, qty, True, "pass", "no risk_limits")

        veto = False
        reasons = []

        # 1. 单笔亏损限额（仅在有真实入场价时检查）
        limit_trade = risk_limits.max_loss_pct_per_trade
        if avg_entry_price > 0 and current_price > 0:
            stop_distance = abs(current_price - avg_entry_price)
            potential_loss = qty * stop_distance
            if potential_loss > 0 and portfolio_equity > 0:
                loss_pct = potential_loss / portfolio_equity
                if loss_pct > limit_trade:
                    veto = True
                    reasons.append(f"单笔损失 {loss_pct:.2%} > 限额 {limit_trade:.2%}")

        # 2. 日亏损限额（仅在有限额时检查）
        if (risk_limits.max_loss_pct_per_day > 0
                and daily_loss_pct > risk_limits.max_loss_pct_per_day):
            veto = True
            reasons.append(
                f"日亏损 {daily_loss_pct:.2%} > 限额 {risk_limits.max_loss_pct_per_day:.2%}"
            )

        if veto:
            return FilterResult(
                passed=False,
                adjusted_qty=0.0,
                limit_check_passed=False,
                mode="veto",
                details="; ".join(reasons) or "loss_limit veto",
            )

        return FilterResult(
            passed=True,
            adjusted_qty=qty,
            limit_check_passed=True,
            mode="pass",
            details=f"loss checks passed (daily={daily_loss_pct:.2%})",
        )
