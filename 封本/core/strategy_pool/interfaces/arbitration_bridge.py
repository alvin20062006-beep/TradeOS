"""ArbitrationInputBridge — 策略池到 Phase 6 仲裁层的接口。

Phase 9 输出 ArbitrationInputBundle（含 PortfolioProposal + StrategyProposal[]）。
Phase 6 正式消费后，产出真正的 ArbitrationDecision[]。
Phase 9 不直接产出 ArbitrationDecision。
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from core.strategy_pool.schemas.arbitration_input import (
    ArbitrationInputBundle,
    PortfolioProposal,
    StrategyProposal,
)
from core.strategy_pool.schemas.portfolio import StrategyPortfolio
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle


class ArbitrationInputBridge:
    """
    策略池 → Phase 6 仲裁层的输入桥接器。

    职责：
    1. 接收 MultiStrategyComposer 产出的 PortfolioProposal
    2. 接收 Phase 4 因子 ID 列表（可选）
    3. 接收 Phase 5 宏观状态引用（可选）
    4. 产出 ArbitrationInputBundle 交付给 Phase 6
    """

    def build(
        self,
        portfolio_proposal: PortfolioProposal,
        supporting_factor_ids: Optional[List[str]] = None,
        regime_context: Optional[Dict] = None,
    ) -> ArbitrationInputBundle:
        """
        构建交付给 Phase 6 的仲裁输入包。

        Args:
            portfolio_proposal: MultiStrategyComposer 产出的组合提案
            supporting_factor_ids: Phase 4 因子 ID 引用（可选）
            regime_context: Phase 5 宏观状态引用（可选）

        Returns:
            ArbitrationInputBundle — Phase 6 正式消费此对象后产出 ArbitrationDecision[]
        """
        return ArbitrationInputBundle(
            bundle_id=f"arb-in-{uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            portfolio_proposal=portfolio_proposal,
            supporting_factor_ids=supporting_factor_ids or [],
            regime_context=regime_context,
        )

    def build_from_portfolio(
        self,
        portfolio: StrategyPortfolio,
        proposals: List[StrategyProposal],
        composite_direction: str,
        composite_strength: float,
        composite_confidence: float,
        supporting_factor_ids: Optional[List[str]] = None,
        regime_context: Optional[Dict] = None,
    ) -> ArbitrationInputBundle:
        """
        从 StrategyPortfolio 直接构建（无需先产出 PortfolioProposal）。

        内部创建 PortfolioProposal 并调用 build()。
        """
        proposal = PortfolioProposal(
            proposal_id=f"pp-{uuid4().hex[:12]}",
            portfolio_id=portfolio.portfolio_id,
            proposals=proposals,
            composite_direction=composite_direction,
            composite_strength=composite_strength,
            composite_confidence=composite_confidence,
            weight_method=portfolio.rebalance_frequency,
        )
        return self.build(proposal, supporting_factor_ids, regime_context)
