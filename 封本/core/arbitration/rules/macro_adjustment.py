"""
Rule 2: Macro Risk Adjustment
===========================

优先级 2。
MacroSignal.risk_off == True 时降低风险敞口。

现有 MacroSignal 字段：
  - risk_on: bool  （True=风险偏好高）
  - regime_confidence: float
  - dominant_themes: list[str]

映射方式：
  - risk_on == True  → risk_adjustment = 1.0（正常）
  - risk_on == False → risk_adjustment = 0.5（风险回避）
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


class MacroAdjustmentRule(ArbitrationRule):
    """
    宏观风险调整规则。

    基于 MacroSignal.risk_on 调整整体风险敞口系数。
    已在 fundamental_veto 之后执行，不受 veto 影响。
    """

    name = "macro_adjustment"
    priority = 2

    RISK_OFF_ADJUSTMENT = 0.5

    def evaluate(
        self,
        bundle: "SignalBundle",
        scores: list["SignalScore"],
        decision: "ArbitrationDecision",
    ) -> None:
        if bundle.macro is None:
            return

        macro = bundle.macro

        # 记录宏观 regime
        if macro.risk_on:
            decision.macro_regime = "risk_on"
            decision.risk_adjustment = 1.0
        else:
            decision.macro_regime = "risk_off"
            decision.risk_adjustment = self.RISK_OFF_ADJUSTMENT

            # 降低所有方向信号的置信度
            for s in scores:
                s.adjusted_confidence *= self.RISK_OFF_ADJUSTMENT
                d = 1 if s.direction.value == "long" else -1
                s.contribution = d * s.adjusted_confidence * s.weight
                s.rule_adjustments.append(
                    f"macro_risk_off: confidence *= {self.RISK_OFF_ADJUSTMENT}"
                )

        decision.rules_applied.append(self.name)
