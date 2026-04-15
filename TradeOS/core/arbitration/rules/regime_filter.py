"""
Rule 5: Market Regime Filter
=========================

优先级 5（最低）。
根据市场状态调整信号强度。

逻辑：
  - TRENDING_UP  → 强化做多信号（×1.2），弱化作空信号（×0.9）
  - TRENDING_DOWN → 强化做空信号（×1.2），弱化作多信号（×0.9）
  - RANGING       → 降低所有方向信号（×0.7）
  - VOLATILE      → 大幅降低所有方向信号（×0.5）

合并规则：取各信号 regime 的众数（排除 UNKNOWN）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from core.schemas import Direction, Regime

from core.arbitration.rules.base import ArbitrationRule

if TYPE_CHECKING:
    from core.arbitration.schemas import (
        ArbitrationDecision,
        SignalBundle,
        SignalScore,
    )


class RegimeFilterRule(ArbitrationRule):
    """
    市场状态过滤规则。

    Phase 6 取各信号 regime 众数作为综合 regime。
    后续可升级为专用的 RegimeDetector 或从 MacroSignal 读取。
    """

    name = "regime_filter"
    priority = 5

    # (信号方向, 当前regime) → 乘数
    REGIME_MULTIPLIERS: dict[tuple[str, str], float] = {
        ("long",   Regime.TRENDING_UP.value): 1.2,
        ("short",  Regime.TRENDING_UP.value): 0.9,
        ("long",   Regime.TRENDING_DOWN.value): 0.9,
        ("short",  Regime.TRENDING_DOWN.value): 1.2,
        ("long",   Regime.RANGING.value): 0.7,
        ("short",  Regime.RANGING.value): 0.7,
        ("long",   Regime.VOLATILE.value): 0.5,
        ("short",  Regime.VOLATILE.value): 0.5,
    }

    def evaluate(
        self,
        bundle: "SignalBundle",
        scores: list["SignalScore"],
        decision: "ArbitrationDecision",
    ) -> None:
        if not scores:
            return

        # 取众数 regime（排除 UNKNOWN）
        regime_counts: dict[str, int] = {}
        for s in scores:
            if s.regime and s.regime != Regime.UNKNOWN:
                regime_counts[s.regime.value] = regime_counts.get(s.regime.value, 0) + 1

        if not regime_counts:
            return

        dominant_regime = max(regime_counts, key=regime_counts.get)

        # 应用乘数
        for s in scores:
            if s.regime is None or s.regime == Regime.UNKNOWN:
                continue
            key = (s.direction.value, s.regime.value)
            mult = self.REGIME_MULTIPLIERS.get(key, 1.0)
            if mult != 1.0:
                s.adjusted_confidence *= mult
                d = 1 if s.direction.value == "long" else -1
                s.contribution = d * s.adjusted_confidence * s.weight
                s.rule_adjustments.append(
                    f"regime_filter: {s.engine_name} regime={s.regime.value} *= {mult}"
                )

        decision.rules_applied.append(f"{self.name}:regime={dominant_regime}")
