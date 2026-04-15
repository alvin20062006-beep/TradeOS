"""
Rule 1: Fundamental Veto
======================

优先级 1（最高）。
D 级评级强制 no_trade。

第一版：作为低频背景约束，不参与投票。
后续可扩展为低权重输入。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.arbitration.rules.base import ArbitrationRule

if TYPE_CHECKING:
    from core.arbitration.schemas import (
        ArbitrationDecision,
        SignalBundle,
        SignalScore,
    )


class FundamentalVetoRule(ArbitrationRule):
    """
    基本盘 veto 规则。

    触发条件：FundamentalReport.rating == "D"
    动作：强制 bias = "no_trade"，所有方向信号贡献归零。
    """

    name = "fundamental_veto"
    priority = 1

    def evaluate(
        self,
        bundle: "SignalBundle",
        scores: list["SignalScore"],
        decision: "ArbitrationDecision",
    ) -> None:
        if bundle.fundamental is None:
            return

        rating = bundle.fundamental.rating
        decision.fundamental_reference = rating

        if rating == "D":
            self._veto_all(scores, decision, f"fundamental_veto: rating={rating}")
            decision.rules_applied.append(self.name)
