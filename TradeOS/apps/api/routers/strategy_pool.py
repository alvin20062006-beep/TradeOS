"""
apps/api/routers/strategy_pool.py — 策略池 API 端点

POST /strategy-pool/propose → MultiStrategyComposer → ArbitrationEngine.arbitrate_portfolio()

约束：
- 不暴露核心 StrategySignalBundle / PortfolioProposal 对象
- 只返回 StrategyPoolProposeResponse（包装 DTO）
- suggestion-only：只输出决策，不改 registry 真值
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends

from apps.auth import User, require_suggest
from apps.dto.api.strategy_pool import (
    StrategyPoolProposeRequest,
    StrategyPoolProposeResponse,
    StrategyPoolDecisionBundle,
    StrategyProposalView,
    StrategySignalBundleView,
)
from apps.dto.api.common import ErrorResponse

router = APIRouter(prefix="/strategy-pool", tags=["Strategy Pool"])


@router.post(
    "/propose",
    response_model=StrategyPoolProposeResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def propose_strategy_pool(
    req: StrategyPoolProposeRequest,
    user: User = Depends(require_suggest),
) -> StrategyPoolProposeResponse:
    """
    策略池提案与仲裁。

    接收策略信号 → MultiStrategyComposer 聚合 → arbitrate_portfolio() 仲裁。
    suggestion-only：只输出决策，不改 registry 真值。
    """
    task_id = f"sp-task-{uuid.uuid4().hex[:12]}"
    ts = req.timestamp or datetime.utcnow()

    decision, proposals_view = _run_strategy_pool_pipeline(req, ts)

    _log_strategy_pool_feedback(user.id, req, decision)

    return StrategyPoolProposeResponse(
        ok=True,
        task_id="immediate",
        status="done",
        message="Strategy pool arbitration completed",
        decision=StrategyPoolDecisionBundle(
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            bias=decision.bias,
            confidence=decision.confidence,
            signal_count=decision.signal_count,
            rules_applied=list(decision.rules_applied) if decision.rules_applied else [],
            timestamp=decision.timestamp or ts,
            arbitration_latency_ms=decision.arbitration_latency_ms,
            source="strategy_pool",
            portfolio_id=req.portfolio_id,
            proposals=proposals_view,
            composite_direction=_composite_dir(proposals_view),
            composite_strength=_composite_strength(proposals_view),
        ),
    )


# ── 内部实现 ────────────────────────────────────────────────

def _run_strategy_pool_pipeline(req: StrategyPoolProposeRequest, ts: datetime):
    """
    策略池全流程：

    1. DTO → 核心对象（内部 import）
    2. MultiStrategyComposer.compose() 聚合策略提案
    3. ArbitrationInputBundle 包装
    4. ArbitrationEngine.arbitrate_portfolio() 产出决策
    5. 核心对象 → DTO 转换（返回展示用）
    """
    from core.arbitration import ArbitrationEngine
    from core.strategy_pool.portfolio.composer import MultiStrategyComposer
    from core.strategy_pool.schemas.arbitration_input import (
        ArbitrationInputBundle,
        PortfolioProposal,
        StrategyProposal,
    )
    from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle

    # 1. DTO → 核心对象
    strategy_proposals: list[StrategyProposal] = []
    bundles_by_strategy: dict[str, list] = {}
    weights: dict[str, float] = {}

    for sp in req.proposals:
        strategy_bundles = [
            StrategySignalBundle(
                bundle_id=b.bundle_id or f"bundle-{sp.proposal_id}-{i}",
                source_strategy_id=sp.strategy_id,
                symbol=req.symbol,
                timestamp=ts,
                direction=b.direction,
                strength=b.strength,
                confidence=b.confidence,
            )
            for i, b in enumerate(sp.bundles)
        ]
        strategy_proposals.append(
            StrategyProposal(
                proposal_id=sp.proposal_id,
                strategy_id=sp.strategy_id,
                bundles=strategy_bundles,
                aggregate_direction=sp.aggregate_direction,
                aggregate_strength=sp.aggregate_strength,
                aggregate_confidence=sp.aggregate_confidence,
                portfolio_weight=sp.portfolio_weight,
            )
        )
        bundles_by_strategy[sp.strategy_id] = strategy_bundles
        weights[sp.strategy_id] = sp.portfolio_weight

    # 2. MultiStrategyComposer 聚合
    composer = MultiStrategyComposer(weight_method=req.weight_method)
    portfolio_proposal = composer.compose(
        bundles_by_strategy=bundles_by_strategy,
        weights=weights,
        portfolio_id=req.portfolio_id,
    )

    # 3. 包装为 ArbitrationInputBundle
    arb_in = ArbitrationInputBundle(
        bundle_id=f"bundle-{req.portfolio_id}",
        portfolio_proposal=portfolio_proposal,
        timestamp=ts,
    )

    # 4. ArbitrationEngine.arbitrate_portfolio()
    engine = ArbitrationEngine()
    decision = engine.arbitrate_portfolio(arb_in, timestamp=ts)

    # 5. 核心对象 → 展示用 DTO
    proposals_view = [
        StrategyProposalView(
            proposal_id=sp.proposal_id,
            strategy_id=sp.strategy_id,
            bundles=[
                StrategySignalBundleView(
                    bundle_id=b.bundle_id,
                    source_strategy_id=b.source_strategy_id,
                    symbol=b.symbol,
                    direction=b.direction,
                    strength=b.strength,
                    confidence=b.confidence,
                )
                for b in sp.bundles
            ],
            aggregate_direction=sp.aggregate_direction,
            aggregate_strength=sp.aggregate_strength,
            aggregate_confidence=sp.aggregate_confidence,
            portfolio_weight=sp.portfolio_weight,
        )
        for sp in strategy_proposals
    ]

    return decision, proposals_view


def _composite_dir(proposals_view: list[StrategyProposalView]) -> str:
    longs = [p for p in proposals_view if p.aggregate_direction == "LONG"]
    shorts = [p for p in proposals_view if p.aggregate_direction == "SHORT"]
    if longs and sum(p.aggregate_strength * p.portfolio_weight for p in longs) > \
            sum(p.aggregate_strength * p.portfolio_weight for p in shorts):
        return "LONG"
    if shorts:
        return "SHORT"
    return "FLAT"


def _composite_strength(proposals_view: list[StrategyProposalView]) -> float:
    if not proposals_view:
        return 0.0
    return sum(p.aggregate_strength * p.portfolio_weight for p in proposals_view) / len(proposals_view)


# ── 审计日志 ────────────────────────────────────────────────

def _log_strategy_pool_feedback(user_id: str, req: StrategyPoolProposeRequest, decision) -> None:
    try:
        from apps.auth import get_auth_service
        auth = get_auth_service()
        auth.log(
            user_id=user_id,
            action="POST /strategy-pool/propose",
            resource="strategy_pool",
            detail={
                "portfolio_id": req.portfolio_id,
                "symbol": req.symbol,
                "proposal_count": len(req.proposals),
                "bias": decision.bias,
                "confidence": decision.confidence,
            },
            result="accepted",
        )
    except Exception:
        pass
