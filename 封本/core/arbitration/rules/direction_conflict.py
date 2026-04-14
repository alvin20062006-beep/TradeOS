"""
Rule 3: Direction Conflict Resolution
=================================

优先级 3。
检测 LONG vs SHORT 方向冲突，按置信度裁决或降级为 hold_bias。

现有信号方向映射：
  - TechnicalSignal / ChanSignal → 自带 direction 字段
  - OrderFlowSignal → 从 book_imbalance 推导（>0 → LONG, <0 → SHORT）
  - SentimentEvent → 从 composite_sentiment 推导（>0.5 → LONG, <0.5 → SHORT）
  - MacroSignal → 从 risk_on 推导（risk_on=True → LONG, risk_on=False → SHORT）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.schemas import Direction

from core.arbitration.rules.base import ArbitrationRule
from core.arbitration.schemas import ConflictRecord

if TYPE_CHECKING:
    from core.arbitration.schemas import (
        ArbitrationDecision,
        ConflictRecord,
        SignalBundle,
        SignalScore,
    )


class DirectionConflictRule(ArbitrationRule):
    """
    方向冲突解决规则。

    策略：
    1. 按信号 direction 分组（LONG vs SHORT）
    2. 若两个方向都有信号 → 检测到冲突
    3. 冲突时：置信度高者胜出，低者贡献归零
    4. 若置信度相近（差值 < 0.1），降级为 hold_bias
    """

    name = "direction_conflict"
    priority = 3
    CONFLICT_THRESHOLD = 0.1  # 置信度差值阈值

    def evaluate(
        self,
        bundle: "SignalBundle",
        scores: list["SignalScore"],
        decision: "ArbitrationDecision",
    ) -> None:
        if not scores:
            return

        # 按信号方向分组
        long_signals = [s for s in scores if s.direction == Direction.LONG]
        short_signals = [s for s in scores if s.direction == Direction.SHORT]

        # 检测冲突：两个方向都有信号
        if not (long_signals and short_signals):
            return

        # 找最高置信度信号
        max_long_conf = max((s.raw_confidence for s in long_signals), default=0.0)
        max_short_conf = max((s.raw_confidence for s in short_signals), default=0.0)

        conflict_record: dict = {
            "signal_a": ",".join(s.engine_name for s in long_signals),
            "signal_b": ",".join(s.engine_name for s in short_signals),
            "direction_a": Direction.LONG,
            "direction_b": Direction.SHORT,
            "resolution": "",
            "rule_applied": self.name,
        }

        diff = abs(max_long_conf - max_short_conf)

        if diff < self.CONFLICT_THRESHOLD:
            # 置信度相近 → 降级为 hold_bias，所有贡献归零
            for s in scores:
                s.contribution = 0.0
                s.rule_adjustments.append("direction_conflict: demoted to hold_bias")
            decision.bias = "hold_bias"
            conflict_record["resolution"] = "confidence_diff < threshold: hold_bias"
        else:
            # 置信度高者胜出
            winner_signals = long_signals if max_long_conf > max_short_conf else short_signals
            loser_signals = short_signals if max_long_conf > max_short_conf else long_signals

            for s in winner_signals:
                s.rule_adjustments.append(
                    f"direction_conflict: winner (conf={s.raw_confidence:.3f})"
                )
            for s in loser_signals:
                s.contribution = 0.0
                s.rule_adjustments.append(
                    f"direction_conflict: loser (conf={s.raw_confidence:.3f})"
                )
            conflict_record["resolution"] = f"winner: {[s.engine_name for s in winner_signals]}"

        decision.conflicts.append(ConflictRecord(**conflict_record))
        decision.rules_applied.append(self.name)
