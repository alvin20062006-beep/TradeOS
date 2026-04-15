"""
Decision Maker
=============

加权投票 → 集成评分 → 生成 ArbitrationDecision。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from core.arbitration.schemas import (
    ArbitrationDecision,
    DecisionRationale,
    SignalScore,
)

from core.arbitration.scorers.ensemble_scorer import EnsembleScorer
from core.arbitration.scorers.signal_scorer import derive_direction_and_confidence, score_signal

if TYPE_CHECKING:
    from core.arbitration.schemas import SignalBundle


class DecisionMaker:
    """
    决策生成器。

    流程：
    1. derive_direction_and_confidence  → DirectionalSignal[]
    2. score_signal                    → SignalScore[]
    3. EnsembleScorer.aggregate         → 更新 decision
    """

    def __init__(self) -> None:
        self._ensemble = EnsembleScorer()

    def decide(self, bundle: "SignalBundle") -> ArbitrationDecision:
        """
        生成最终仲裁决策。

        Args:
            bundle: SignalBundle

        Returns:
            ArbitrationDecision
        """
        ts = bundle.timestamp

        # 构建初始决策
        decision = ArbitrationDecision(
            decision_id=str(uuid.uuid4()),
            timestamp=ts,
            symbol=bundle.symbol,
            bias="no_trade",
            confidence=0.0,
            signal_count=bundle.signals_present,
        )

        # 提取方向信号
        directional = derive_direction_and_confidence(bundle)

        # 评分
        scores: List[SignalScore] = [score_signal(ds) for ds in directional]

        # 集成
        self._ensemble.aggregate(scores, decision)

        # 构建理由链
        decision.rationale = [
            DecisionRationale(
                signal_name=s.engine_name,
                direction=s.direction,
                confidence=s.raw_confidence,
                weight=s.weight,
                contribution=s.contribution,
                rule_adjustments=s.rule_adjustments,
            )
            for s in scores
        ]

        return decision
