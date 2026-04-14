"""
Rule 4: Confidence Weight Adjustment
=================================

优先级 4。
根据信号类型和历史准确率调整权重。

权重表（Phase 6 初始版本，可配置）：
  technical    → 1.0  （基准）
  chan         → 0.9  （结构信号，适用性稍低）
  orderflow    → 1.1  （短期资金信号，置信度高）
  sentiment    → 0.8  （情绪波动大，权重适度降低）
  macro        → 0.9  （宏观信号频率低）
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


class ConfidenceWeightRule(ArbitrationRule):
    """
    置信度加权规则。

    Phase 6 初始权重为硬编码表。
    后续可扩展为从配置或历史回测数据加载。
    """

    name = "confidence_weight"
    priority = 4

    # 初始权重表（可覆盖）
    DEFAULT_WEIGHTS: dict[str, float] = {
        "technical": 1.0,
        "chan": 0.9,
        "orderflow": 1.1,
        "sentiment": 0.8,
        "macro": 0.9,
    }

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or self.DEFAULT_WEIGHTS

    def evaluate(
        self,
        bundle: "SignalBundle",
        scores: list["SignalScore"],
        decision: "ArbitrationDecision",
    ) -> None:
        for s in scores:
            w = self._weights.get(s.engine_name, 1.0)
            if w != 1.0:
                s.weight = w
                s.adjusted_confidence = s.raw_confidence
                s.rule_adjustments.append(f"confidence_weight: {s.engine_name} *= {w}")

        decision.rules_applied.append(self.name)
