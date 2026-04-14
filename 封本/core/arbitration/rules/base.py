"""
Arbitration Rules — Base
=======================

所有仲裁规则必须继承 ArbitrationRule 并实现 evaluate()。
规则按优先级（priority，数字越小越高）顺序执行。

优先级约定：
    1   → fundamental_veto（最高）
    2   → macro_adjustment
    3   → direction_conflict
    4   → confidence_weight
    5   → regime_filter（最低）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.arbitration.schemas import (
        ArbitrationDecision,
        DecisionRationale,
        DirectionalSignal,
        SignalBundle,
        SignalScore,
    )


class ArbitrationRule(ABC):
    """
    仲裁规则抽象基类。

    所有规则接收同一个 SignalBundle 和当前评分状态，
    返回调整后的状态（通过修改传入对象）。

    规则设计原则：
    - 无状态：evaluate() 必须是幂等的，不依赖外部状态
    - 可组合：多个规则可以叠加效果
    - 可追溯：每次调整必须追加 rule_adjustments 记录
    """

    # 子类必须设置
    name: str = "base"
    priority: int = 99  # 数字越小优先级越高

    @abstractmethod
    def evaluate(
        self,
        bundle: "SignalBundle",
        scores: List["SignalScore"],
        decision: "ArbitrationDecision",
    ) -> None:
        """
        评估规则并调整评分和决策。

        Args:
            bundle:        原始信号包
            scores:        当前各信号的评分列表（in-place 修改）
            decision:      当前仲裁决策（in-place 修改）
        """
        ...

    # ─────────────────────────────────────────────────────
    # Shared helpers for subclasses
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _apply_weight_adjustment(
        scores: List["SignalScore"],
        engine_name: str,
        multiplier: float,
        reason: str,
    ) -> None:
        """调整指定引擎信号的权重。"""
        for s in scores:
            if s.engine_name == engine_name:
                s.weight *= multiplier
                s.adjusted_confidence *= multiplier
                # 重新计算贡献
                d = 1 if s.direction.value == "long" else -1
                s.contribution = d * s.adjusted_confidence * s.weight
                s.rule_adjustments.append(reason)

    @staticmethod
    def _veto_all(scores: List["SignalScore"], decision: "ArbitrationDecision", reason: str) -> None:
        """强制所有方向信号贡献归零。"""
        for s in scores:
            s.contribution = 0.0
            s.adjusted_confidence = 0.0
            s.rule_adjustments.append(f"veto: {reason}")
        decision.bias = "no_trade"
        decision.confidence = 0.0
        decision.fundamental_veto_triggered = True

    @staticmethod
    def _normalize_scores(scores: List["SignalScore"]) -> None:
        """重新计算所有信号的 contribution（供 evaluate 末尾调用）。"""
        for s in scores:
            d = 1 if s.direction.value == "long" else -1
            s.contribution = d * s.adjusted_confidence * s.weight
