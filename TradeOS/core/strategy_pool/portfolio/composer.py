"""MultiStrategyComposer — 多策略信号聚合与冲突仲裁。"""
from __future__ import annotations

from typing import Dict, List
from uuid import uuid4

from core.strategy_pool.schemas.arbitration_input import PortfolioProposal, StrategyProposal
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle


class MultiStrategyComposer:
    """
    多策略信号聚合器。

    职责：
    1. 将多个策略的 StrategySignalBundle 按 symbol 聚合
    2. 冲突仲裁（directional priority / weighted vote）
    3. 产出 PortfolioProposal（含 StrategyProposal[]）
    """

    def __init__(self, weight_method: str = "equal") -> None:
        self.weight_method = weight_method

    def compose(
        self,
        bundles_by_strategy: Dict[str, List[StrategySignalBundle]],
        weights: Dict[str, float],
        portfolio_id: str,
    ) -> PortfolioProposal:
        """
        聚合多策略信号，产出 PortfolioProposal。

        Args:
            bundles_by_strategy: {strategy_id: [StrategySignalBundle]}
            weights: {strategy_id: weight (0-1)}
            portfolio_id: 组合 ID
        """
        proposals: List[StrategyProposal] = []

        for strategy_id, bundles in bundles_by_strategy.items():
            prop = self._make_strategy_proposal(
                strategy_id, bundles, weights.get(strategy_id, 0.0)
            )
            proposals.append(prop)

        composite = self._aggregate_proposals(proposals)
        return PortfolioProposal(
            proposal_id=f"pp-{uuid4().hex[:12]}",
            portfolio_id=portfolio_id,
            proposals=proposals,
            composite_direction=composite["direction"],
            composite_strength=composite["strength"],
            composite_confidence=composite["confidence"],
            weight_method=self.weight_method,
        )

    def _make_strategy_proposal(
        self,
        strategy_id: str,
        bundles: List[StrategySignalBundle],
        weight: float,
    ) -> StrategyProposal:
        """将一个策略的 SignalBundle[] 聚合成 StrategyProposal。"""
        if not bundles:
            return StrategyProposal(
                proposal_id=f"sp-{uuid4().hex[:12]}",
                strategy_id=strategy_id,
                bundles=[],
                aggregate_direction="FLAT",
                aggregate_strength=0.0,
                aggregate_confidence=0.0,
                portfolio_weight=weight,
            )

        # 按 direction 分组
        longs = [b for b in bundles if b.direction == "LONG"]
        shorts = [b for b in bundles if b.direction == "SHORT"]

        # 加权信号方向仲裁：strength × weight 的均值
        def weighted_strength(bundles: List[StrategySignalBundle]) -> float:
            if not bundles:
                return 0.0
            return sum(b.strength * weight for b in bundles) / len(bundles)

        long_strength = weighted_strength(longs)
        short_strength = weighted_strength(shorts)

        if long_strength > short_strength:
            direction = "LONG"
            strength = long_strength
        elif short_strength > long_strength:
            direction = "SHORT"
            strength = short_strength
        else:
            direction = "FLAT"
            strength = 0.0

        confidence = (
            sum(b.confidence * weight for b in bundles)
            / (len(bundles) or 1)
        )

        return StrategyProposal(
            proposal_id=f"sp-{uuid4().hex[:12]}",
            strategy_id=strategy_id,
            bundles=bundles,
            aggregate_direction=direction,
            aggregate_strength=strength,
            aggregate_confidence=confidence,
            portfolio_weight=weight,
        )

    def _aggregate_proposals(
        self, proposals: List[StrategyProposal]
    ) -> Dict:
        """将 StrategyProposal[] 聚合成组合级结论。"""
        longs = [p for p in proposals if p.aggregate_direction == "LONG"]
        shorts = [p for p in proposals if p.aggregate_direction == "SHORT"]

        long_w = sum(p.aggregate_strength * p.portfolio_weight for p in longs)
        short_w = sum(p.aggregate_strength * p.portfolio_weight for p in shorts)

        if long_w > short_w:
            direction = "LONG"
            strength = long_w
        elif short_w > long_w:
            direction = "SHORT"
            strength = short_w
        else:
            direction = "FLAT"
            strength = 0.0

        confidence = (
            sum(p.aggregate_confidence * p.portfolio_weight for p in proposals)
            / (len(proposals) or 1)
        )

        return {"direction": direction, "strength": strength, "confidence": confidence}
