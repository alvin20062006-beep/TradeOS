"""
apps/api/routers/arbitration.py 鈥?浠茶灞?API 绔偣

POST /arbitration/run        鈫?鏃у叆鍙ｏ紙娑堣垂 Phase 5 淇″彿锛?POST /arbitration/run-portfolio 鈫?鏂板叆鍙ｏ紙娑堣垂 Phase 9 绛栫暐姹狅級
AI 閫氳繃 API DTO 鎺ュ叆锛岀姝㈢洿鎺ョ粦瀹?ArbitrationDecision銆?"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from apps.auth import User, require_suggest
from apps.dto.api.arbitration import (
    ArbitrationResponse,
    ArbitrationRunRequest,
    DecisionRationaleView,
    PortfolioArbitrationRequest,
)
from apps.dto.api.common import ErrorResponse

router = APIRouter(prefix="/arbitration", tags=["Arbitration"])
logger = logging.getLogger(__name__)


@router.post(
    "/run",
    response_model=ArbitrationResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def run_arbitration(
    req: ArbitrationRunRequest,
    user: User = Depends(require_suggest),
) -> ArbitrationResponse:
    """
    鏃у叆鍙ｄ徊瑁侊紙娑堣垂 Phase 5 淇″彿锛夈€?
    suggestion-only锛氬彧杈撳嚭 ArbitrationDecision锛屼笉鏀?registry 鐪熷€笺€?    AI 鍙€氳繃姝ょ鐐逛骇鐢熷缓璁紝寤鸿缁撴灉鍐欏叆 FeedbackRegistry锛坅ppend-only锛夈€?    """
    decision = _call_arbitration_engine(req)

    _log_arbitration_feedback(user.id, req, decision)

    return _to_arb_response(decision, source="arbitration")


@router.post(
    "/run-portfolio",
    response_model=ArbitrationResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def run_portfolio_arbitration(
    req: PortfolioArbitrationRequest,
    user: User = Depends(require_suggest),
) -> ArbitrationResponse:
    """
    鏂板叆鍙ｄ徊瑁侊紙娑堣垂 Phase 9 绛栫暐姹狅級銆?
    鎺ユ敹 StrategySignalBundle[] 搴忓垪鍖栫殑璇锋眰浣擄紝
    鍐呴儴杞崲鍚庤皟鐢?ArbitrationEngine.arbitrate_portfolio()銆?    """
    decision = _call_portfolio_arbitration(req)

    _log_portfolio_feedback(user.id, req, decision)

    return _to_arb_response(decision, source="portfolio")


# 鈹€鈹€ 鍐呴儴璋冪敤 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _call_arbitration_engine(req: ArbitrationRunRequest):
    """璋冪敤 Phase 6 ArbitrationEngine.arbitrate()銆?"""
    from core.arbitration import ArbitrationEngine
    from core.schemas import Direction, Regime, TechnicalSignal

    engine = ArbitrationEngine()

    # 鏋勫缓 Phase 5 TechnicalSignal锛堟渶灏忓彲鐢ㄨ緭鍏ワ級
    # Direction enum values are lowercase ('long'), DTO uses uppercase ('LONG')
    dir_map = {"LONG": "long", "SHORT": "short", "FLAT": "flat"}
    direction = Direction(dir_map.get(req.direction, "flat"))

    technical = TechnicalSignal(
        engine_name="technical",
        symbol=req.symbol,
        timestamp=req.timestamp or datetime.utcnow(),
        direction=direction,
        confidence=req.confidence,
        strength=req.strength,
        regime=Regime(req.regime),
    )

    return engine.arbitrate(
        symbol=req.symbol,
        timestamp=req.timestamp,
        technical=technical,
    )


def _call_portfolio_arbitration(req: PortfolioArbitrationRequest):
    """璋冪敤 Phase 10 ArbitrationEngine.arbitrate_portfolio()銆?"""
    from core.arbitration import ArbitrationEngine
    from core.strategy_pool.schemas.arbitration_input import (
        ArbitrationInputBundle,
        PortfolioProposal,
        StrategyProposal,
    )
    from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle

    engine = ArbitrationEngine()
    ts = req.timestamp or datetime.utcnow()

    proposals = []
    for sp in req.proposals:
        bundle = StrategySignalBundle(
            bundle_id=f"bundle-{sp.proposal_id}-1",
            source_strategy_id=sp.strategy_id,
            symbol=req.symbol,
            timestamp=ts,
            direction=sp.aggregate_direction,
            strength=sp.aggregate_strength,
            confidence=sp.aggregate_confidence,
        )
        proposals.append(
            StrategyProposal(
                proposal_id=sp.proposal_id,
                strategy_id=sp.strategy_id,
                bundles=[bundle],
                aggregate_direction=sp.aggregate_direction,
                aggregate_strength=sp.aggregate_strength,
                aggregate_confidence=sp.aggregate_confidence,
                portfolio_weight=sp.portfolio_weight,
            )
        )

    pp = PortfolioProposal(
        proposal_id=req.portfolio_id,
        portfolio_id=req.portfolio_id,
        proposals=proposals,
        composite_direction=req.proposals[0].aggregate_direction if req.proposals else "FLAT",
        composite_strength=req.proposals[0].aggregate_strength if req.proposals else 0.0,
        composite_confidence=req.proposals[0].aggregate_confidence if req.proposals else 0.0,
        weight_method="equal",
    )

    arb_in = ArbitrationInputBundle(
        bundle_id=f"bundle-{req.portfolio_id}",
        portfolio_proposal=pp,
        timestamp=ts,
    )

    return engine.arbitrate_portfolio(arb_in, timestamp=ts)


# 鈹€鈹€ 杞崲涓烘牳蹇?鈫?DTO 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _to_arb_response(decision, source: str) -> ArbitrationResponse:
    """鏍稿績 ArbitrationDecision 鈫?API ArbitrationResponse DTO銆?"""
    # rules_applied: List[str]锛堣鍒欏悕绉板垪琛級
    # rationale: List[DecisionRationale]锛堜俊鍙风悊鐢卞垪琛級
    return ArbitrationResponse(
        ok=True,
        decision_id=decision.decision_id,
        symbol=decision.symbol,
        bias=decision.bias,
        confidence=decision.confidence,
        signal_count=decision.signal_count,
        rules_applied=list(decision.rules_applied) if decision.rules_applied else [],
        rationale=[
            DecisionRationaleView(
                signal_name=r.signal_name,
                direction=r.direction,
                confidence=r.confidence,
                weight=r.weight,
                contribution=r.contribution,
                rule_adjustments=r.rule_adjustments,
            )
            for r in (decision.rationale or [])
            if r is not None
        ],
        timestamp=decision.timestamp or datetime.utcnow(),
        arbitration_latency_ms=decision.arbitration_latency_ms,
        source=source,
    )


# 鈹€鈹€ 瀹¤鏃ュ織 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _log_arbitration_feedback(user_id: str, req: ArbitrationRunRequest, decision) -> None:
    try:
        from apps.auth import get_auth_service

        auth = get_auth_service()
        auth.log(
            user_id=user_id,
            action="POST /arbitration/run",
            resource="arbitration",
            detail={
                "symbol": req.symbol,
                "direction": req.direction,
                "bias": decision.bias,
                "confidence": decision.confidence,
            },
            result="accepted",
        )
    except Exception as exc:
        logger.warning("Failed to append arbitration auth audit", exc_info=True)


def _log_portfolio_feedback(user_id: str, req: PortfolioArbitrationRequest, decision) -> None:
    try:
        from apps.auth import get_auth_service

        auth = get_auth_service()
        auth.log(
            user_id=user_id,
            action="POST /arbitration/run-portfolio",
            resource="arbitration",
            detail={
                "portfolio_id": req.portfolio_id,
                "symbol": req.symbol,
                "proposal_count": len(req.proposals),
                "bias": decision.bias,
                "confidence": decision.confidence,
            },
            result="accepted",
        )
    except Exception as exc:
        logger.warning("Failed to append portfolio arbitration auth audit", exc_info=True)
