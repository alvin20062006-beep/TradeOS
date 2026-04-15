"""
apps/api/routers/arbitration.py — 仲裁层 API 端点

POST /arbitration/run        → 旧入口（消费 Phase 5 信号）
POST /arbitration/run-portfolio → 新入口（消费 Phase 9 策略池）
AI 通过 API DTO 接入，禁止直接绑定 ArbitrationDecision。
"""

from __future__ import annotations

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
    旧入口仲裁（消费 Phase 5 信号）。

    suggestion-only：只输出 ArbitrationDecision，不改 registry 真值。
    AI 可通过此端点产生建议，建议结果写入 FeedbackRegistry（append-only）。
    """
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
    新入口仲裁（消费 Phase 9 策略池）。

    接收 StrategySignalBundle[] 序列化的请求体，
    内部转换后调用 ArbitrationEngine.arbitrate_portfolio()。
    """
    decision = _call_portfolio_arbitration(req)

    _log_portfolio_feedback(user.id, req, decision)

    return _to_arb_response(decision, source="portfolio")


# ── 内部调用 ────────────────────────────────────────────────

def _call_arbitration_engine(req: ArbitrationRunRequest):
    """调用 Phase 6 ArbitrationEngine.arbitrate()。"""
    from core.arbitration import ArbitrationEngine
    from core.schemas import Direction, Regime, TechnicalSignal

    engine = ArbitrationEngine()

    # 构建 Phase 5 TechnicalSignal（最小可用输入）
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
    """调用 Phase 10 ArbitrationEngine.arbitrate_portfolio()。"""
    from core.arbitration import ArbitrationEngine
    from core.strategy_pool.schemas.arbitration_input import (
        ArbitrationInputBundle,
        PortfolioProposal,
        StrategyProposal,
    )
    from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle

    engine = ArbitrationEngine()
    ts = req.timestamp or datetime.utcnow()

    # 构建 StrategySignalBundle[]（从 DTO 转换，不引用核心类型）
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


# ── 转换为核心 → DTO ────────────────────────────────────────

def _to_arb_response(decision, source: str) -> ArbitrationResponse:
    """核心 ArbitrationDecision → API ArbitrationResponse DTO。"""
    # rules_applied: List[str]（规则名称列表）
    # rationale: List[DecisionRationale]（信号理由列表）
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


# ── 审计日志 ────────────────────────────────────────────────

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
    except Exception:
        pass


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
    except Exception:
        pass
