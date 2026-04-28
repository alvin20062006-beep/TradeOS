"""
apps/api/routers/risk.py 鈥?椋庢帶寮曟搸 API 绔偣

POST /risk/calculate锛氳Е鍙?Phase 7 椋庢帶璁＄畻锛坰uggestion-only锛?AI 閫氳繃 API DTO 鎺ュ叆锛岀姝㈢洿鎺ョ粦瀹氭牳蹇?PositionPlan銆?"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends

from apps.auth import User, require_suggest
from apps.dto.api.audit import LimitCheckView
from apps.dto.api.risk import (
    ExecutionPlanView,
    PositionPlanView,
    RiskCalculateRequest,
)
from apps.dto.api.common import ErrorResponse

router = APIRouter(prefix="/risk", tags=["Risk"])
logger = logging.getLogger(__name__)


@router.post(
    "/calculate",
    response_model=PositionPlanView,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def calculate_risk(
    req: RiskCalculateRequest,
    user: User = Depends(require_suggest),
) -> PositionPlanView:
    """
    瑙﹀彂 Phase 7 椋庢帶璁＄畻銆?
    suggestion-only锛氬彧杈撳嚭 PositionPlan锛屼笉鏀?registry 鐪熷€笺€?    AI 鍙€氳繃姝ょ鐐逛骇鐢熼鎺у缓璁紝寤鸿缁撴灉鍐欏叆 FeedbackRegistry锛坅ppend-only锛夈€?    """
    plan = _call_risk_engine(req)

    _log_risk_feedback(user.id, req, plan)

    return _to_plan_view(plan)


# 鈹€鈹€ 鍐呴儴璋冪敤 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _call_risk_engine(req: RiskCalculateRequest):
    """
    璋冪敤 Phase 7 RiskEngine.calculate()銆?    鍐呴儴 import锛岄伩鍏嶄骇鍝佸眰寮哄埗渚濊禆鏍稿績鍚姩銆?    """
    from core.risk.engine import RiskEngine
    from core.schemas import ArbitrationDecision, Direction, Portfolio

    direction_map = {
        "LONG": Direction.LONG,
        "SHORT": Direction.SHORT,
        "FLAT": Direction.FLAT,
    }
    decision_direction = direction_map.get(req.direction or req.target_direction or "FLAT", Direction.FLAT)

    decision = ArbitrationDecision(
        decision_id=req.decision_id,
        timestamp=req.timestamp or datetime.utcnow(),
        symbol=req.symbol,
        bias=req.bias,
        confidence=req.confidence,
        direction=decision_direction,
        target_direction=req.target_direction or (decision_direction.value if hasattr(decision_direction, "value") else str(decision_direction)),
        risk_adjustment=req.risk_adjustment,
        no_trade_reason=req.no_trade_reason,
        entry_permission=req.bias not in ("no_trade", "hold_bias"),
        signal_count=1,
    )

    portfolio = Portfolio(
        timestamp=req.timestamp or datetime.utcnow(),
        total_equity=req.portfolio_value,
        cash=req.portfolio_value,
        peak_equity=req.portfolio_value,
        positions=[],
    )

    # 璋冪敤椋庢帶寮曟搸
    existing_dir = direction_map.get(req.existing_direction, Direction.FLAT)

    engine = RiskEngine()
    return engine.calculate(
        decision=decision,
        portfolio=portfolio,
        current_price=req.current_price,
        existing_position_qty=req.existing_position,
        existing_direction=existing_dir,
        avg_entry_price=req.avg_entry_price,
        regime_name=req.regime,
    )


def _to_plan_view(plan) -> PositionPlanView:
    """鏍稿績 PositionPlan 鈫?API PositionPlanView DTO銆?"""
    veto_reason = None
    veto_source = None
    decision_gate_reason = None
    limit_checks = []
    for lc in (plan.limit_checks or []):
        limit_checks.append(
            LimitCheckView(
                filter_name=lc.limit_name,
                passed=lc.passed,
                mode=lc.mode,
                raw_qty=lc.raw_qty,
                adjusted_qty=lc.actual_value,
                reason=str(lc.details) if lc.details else "",
            )
        )
        if plan.veto_triggered and not lc.passed and veto_reason is None:
            veto_reason = str(lc.details) if lc.details else f"{lc.limit_name} veto"
            veto_source = lc.limit_name

    exec_plan = None
    if plan.execution_plan is not None and not plan.veto_triggered:
        ep = plan.execution_plan
        ep_algo = ep.algorithm.value if hasattr(ep.algorithm, "value") else str(ep.algorithm)
        ep_ts = ep.timestamp or datetime.utcnow()
        exec_plan = ExecutionPlanView(
            algorithm=ep_algo,
            limit_price=ep.limit_price,
            stop_price=None,  # ExecutionPlan 浣跨敤 worst_price锛孌TO 鏄犲皠涓?None
            timestamp=ep_ts,
        )

    plan_dir = plan.direction.value if hasattr(plan.direction, "value") else str(plan.direction)
    exec_act = plan.exec_action.value if hasattr(plan.exec_action, "value") else str(plan.exec_action)
    ts = plan.timestamp or datetime.utcnow()
    if plan.veto_triggered and not veto_reason:
        veto_reason = (plan.veto_reasons or [None])[0]
        if veto_reason:
            if str(veto_reason).startswith("sizing_zero_quantity"):
                veto_source = "sizing"
                decision_gate_reason = str(veto_reason)
            elif "arbitration" in str(veto_reason) or "no_trade" in str(veto_reason):
                veto_source = "arbitration"
                decision_gate_reason = str(veto_reason)
            else:
                veto_source = "decision_gate"
                decision_gate_reason = str(veto_reason)

    return PositionPlanView(
        ok=True,
        plan_id=plan.plan_id,
        symbol=plan.symbol,
        direction=plan_dir,
        exec_action=exec_act,
        final_quantity=plan.final_quantity,
        veto_triggered=plan.veto_triggered,
        veto_reason=veto_reason,
        veto_source=veto_source,
        decision_gate_reason=decision_gate_reason,
        limit_checks=limit_checks,
        execution_plan=exec_plan,
        timestamp=ts,
    )


def _log_risk_feedback(user_id: str, req: RiskCalculateRequest, plan) -> None:
    try:
        from apps.auth import get_auth_service

        auth = get_auth_service()
        auth.log(
            user_id=user_id,
            action="POST /risk/calculate",
            resource="risk",
            detail={
                "symbol": req.symbol,
                "bias": req.bias,
                "final_quantity": plan.final_quantity,
                "veto_triggered": plan.veto_triggered,
            },
            result="accepted",
        )
    except Exception as exc:
        logger.warning("Failed to append risk auth audit", exc_info=True)
