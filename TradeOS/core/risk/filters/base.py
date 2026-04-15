"""
Risk Filters
===========

7种风控过滤器（CorrelationLimitFilter 为占位 / no-op），按优先级执行。
每个过滤器接收当前仓位，返回 FilterResult（含 mode: pass/cap/veto）。

mode 语义：
  "pass"  — 数量在限额内，无调整，正常通过
  "cap"   — 数量超出限额，被压缩调整后通过（passed=True，但 qty 被改小）
  "veto"  — 数量严重违规，被拒绝（passed=False，qty=0）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class FilterResult:
    """
    单个过滤器结果。

    Attributes
    ----------
    passed : bool
        是否通过（veto 时为 False，其余为 True）
    adjusted_qty : float
        调整后数量（cap 时 < 原数量；pass/veto 时 = 传入数量）
    limit_check_passed : bool
        限额本身是否通过（cap 时仍为 True，因为限额值本身无错）
    mode : str
        过滤器行为模式：
        "pass" — 限额内，无干预
        "cap"  — 超出限额，被压缩（passed=True，qty 减小）
        "veto" — 严重违规，被拒绝（passed=False，qty=0）
    details : str
        人类可读说明
    """
    passed: bool
    adjusted_qty: float
    limit_check_passed: bool
    mode: str = "pass"   # "pass" | "cap" | "veto"
    details: str = ""


class RiskFilter(ABC):
    """
    风控过滤器抽象基类。

    所有过滤器必须实现 apply() 方法，并确保 _filter() 返回时
    填写正确的 mode 字段。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """过滤器名称。"""
        ...

    def apply(
        self,
        qty: float,
        direction_sign: int,
        **context,
    ) -> FilterResult:
        """
        应用过滤器。

        Parameters
        ----------
        qty : float
            当前待过滤数量
        direction_sign : int
            方向符号：+1 = LONG，-1 = SHORT

        context 关键字参数（各子类使用不同子集）：
        ----
        risk_limits : RiskLimits
        portfolio_equity : float
        current_price : float
        market_context : MarketContext
        existing_position_qty : float
        avg_entry_price : float
        current_drawdown_pct : float
        daily_loss_pct : float
        positions : list[Position]
        """
        if qty <= 0:
            return FilterResult(
                passed=True,
                adjusted_qty=0.0,
                limit_check_passed=True,
                mode="pass",
                details="qty=0, skip filter",
            )
        return self._filter(qty=qty, direction_sign=direction_sign, **context)

    @abstractmethod
    def _filter(self, **kwargs) -> FilterResult:
        """子类实现具体过滤逻辑，必须返回带 mode 的 FilterResult。"""
        ...
