"""CorrelationLimitFilter — max_correlation."""
from core.risk.filters.base import FilterResult, RiskFilter


class CorrelationLimitFilter(RiskFilter):
    """
    占位过滤器（placeholder / no-op）。

    当前始终返回 passed=True，mode="pass"，不执行真实相关性检查。

    TODO (Phase 8+): 实现真实相关性限额检查：
      1. 从 Position 获取新仓位的 sector 标签
      2. 从 correlation_matrix 查询同 sector 的相关性
      3. 超过阈值则 cap 或 veto
    """
    """
    相关性限额过滤器。

    检查新仓位的 symbol 相关性：
    - 若已有同方向同板块仓位，相关性过高则警告
    - 若有反向相关，现有仓位和新仓位方向相反（对冲）则放宽
    """

    name = "max_correlation"

    def _filter(
        self,
        qty,
        direction_sign,
        risk_limits=None,
        existing_position_symbols=None,
        correlation_matrix=None,
        **kwargs,
    ):
        if risk_limits is None:
            return FilterResult(True, qty, True, "pass", "no risk_limits")

        if (
            existing_position_symbols is None
            or not existing_position_symbols
            or correlation_matrix is None
        ):
            return FilterResult(True, qty, True, "pass", "no correlation data")

        return FilterResult(
            passed=True,
            adjusted_qty=qty,
            limit_check_passed=True,
            mode="pass",
            details="correlation check: placeholder (requires sector tagging)",
        )
