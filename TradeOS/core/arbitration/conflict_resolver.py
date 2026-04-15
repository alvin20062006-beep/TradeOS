"""
Conflict Resolver
================

应用方向冲突检测与解决规则。
内部委托给 DirectionConflictRule。

设计说明：
冲突解决已在 DirectionConflictRule (priority=3) 中实现，
本模块作为显式入口，提供冲突检测报告。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from core.arbitration.schemas import ConflictRecord

from core.arbitration.rules.direction_conflict import DirectionConflictRule

if TYPE_CHECKING:
    from core.arbitration.schemas import (
        ArbitrationDecision,
        SignalBundle,
        SignalScore,
    )


class ConflictResolver:
    """
    冲突解决器。

    使用 DirectionConflictRule 检测并解决方向冲突。
    """

    def __init__(self) -> None:
        self._rule = DirectionConflictRule()

    def resolve(
        self,
        bundle: "SignalBundle",
        scores: List["SignalScore"],
        decision: "ArbitrationDecision",
    ) -> List[ConflictRecord]:
        """
        检测并解决方向冲突。

        Args:
            bundle:   信号包
            scores:   信号评分列表
            decision: 仲裁决策

        Returns:
            冲突记录列表（可能在 decision.conflicts 中）
        """
        before_count = len(decision.conflicts)
        self._rule.evaluate(bundle, scores, decision)
        after_count = len(decision.conflicts)
        return decision.conflicts[before_count:after_count]
