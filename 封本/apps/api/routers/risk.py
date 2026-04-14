"""
apps/api/routers/risk.py — 风控引擎 API 端点

POST /risk/calculate：触发 Phase 7 风控计算（suggestion-only）
AI 通过 API DTO 接入，禁止直接绑定核心 PositionPlan。
"""

from __future__ import annotations

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
    触发 Phase 7 风控计算。

    suggestion-only：只输出 PositionPlan，不改 registry 真值。
    AI 可通过此端点产生风控建议，建议结果写入 FeedbackRegistry（append-only）。
    """
    plan = _call_risk_engine(req)

    _log_risk_feedback(user.id, req, plan)

    return _to_plan_view(plan)


# ── 内部调用 ────────────────────────────────────────────────

def _call_risk_engine(req: RiskCalculateRequest):
    """
    调用 Phase 7 RiskEngine.calculate()。
    内部 import，避免产品层强制依赖核心启动。
    """
    from core.risk.engine import RiskEngine

    # 构建 Phase 6 ArbitrationDecision 摘要（最小输入）
    from core.arbitration.schemas import ArbitrationDecision
    from core.schemas import Portfolio

    decision = ArbitrationDecision(
        decision_id=req.decision_id,
        symbol=req.symbol,
        bias=req.bias,
        confidence=req.confidence,
        signal_count=1,
        timestamp=req.timestamp or datetime.utcnow(),
    )

    # 构建 Portfolio 状态
    portfolio = Portfolio(
        timestamp=req.timestamp or datetime.utcnow(),
        total_equity=req.portfolio_value,
        cash=req.portfolio_value,
        peak_equity=req.portfolio_value,
        positions=[],  # 首批：简化处理，无现有持仓
    )

    # 调用风控引擎
    dir_map = {"LONG": "long", "SHORT": "short", "FLAT": "flat"}
    existing_dir = dir_map.get(req.existing_direction, "flat")

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
    """核心 PositionPlan → API PositionPlanView DTO。"""
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

    exec_plan = None
    if plan.execution_plan is not None and not plan.veto_triggered:
        ep = plan.execution_plan
        ep_algo = ep.algorithm.value if hasattr(ep.algorithm, "value") else str(ep.algorithm)
        ep_ts = ep.timestamp or datetime.utcnow()
        exec_plan = ExecutionPlanView(
            algorithm=ep_algo,
            limit_price=ep.limit_price,
            stop_price=None,  # ExecutionPlan 使用 worst_price，DTO 映射为 None
            timestamp=ep_ts,
        )

    plan_dir = plan.direction.value if hasattr(plan.direction, "value") else str(plan.direction)
    exec_act = plan.exec_action.value if hasattr(plan.exec_action, "value") else str(plan.exec_action)
    ts = plan.timestamp or datetime.utcnow()

    return PositionPlanView(
        ok=True,
        plan_id=plan.plan_id,
        symbol=plan.symbol,
        direction=plan_dir,
        exec_action=exec_act,
        final_quantity=plan.final_quantity,
        veto_triggered=plan.veto_triggered,
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
    except Exception:
        pass
