"""
apps/api/routers/pipeline.py 鈥?鍏ㄩ摼璺紪鎺?API 绔偣

POST /pipeline/run-full锛氫覆鑱?Phase 5 鈫?6 鈫?7
    GET /pipeline/status/{task_id}锛氭煡璇?pipeline 鐘舵€?
绾︽潫锛?- 绾?orchestration锛屼笉閲嶅啓浠讳綍闃舵閫昏緫
- 涓茶仈鐜版湁鍏紑 API/鏂规硶
- 涓嶆毚闇叉牳蹇冨唴閮ㄥ璞?"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from apps.auth import User, require_suggest
from apps.dto.api.pipeline import (
    PipelineRunFullRequest,
    PipelineRunFullResponse,
    PipelinePhaseResult,
    PipelineDecisionView,
    PipelinePlanView,
)
from apps.dto.api.common import ErrorResponse
from apps.dto.api.live import (
    LiveDataSummaryView,
    LiveModuleView,
    LivePipelineResponse,
    LiveRunRequest,
)

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])
logger = logging.getLogger(__name__)


@router.post(
    "/run-full",
    response_model=PipelineRunFullResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def run_full_pipeline(
    req: PipelineRunFullRequest,
    user: User = Depends(require_suggest),
) -> PipelineRunFullResponse:
    """
    鍏ㄩ摼璺紪鎺掞紙Phase 5 鈫?6 鈫?7锛夈€?
    涓茶仈鐜版湁鍏紑鏂规硶锛屼笉閲嶅啓闃舵閫昏緫銆?    suggestion-only锛氬彧杈撳嚭鍐崇瓥鍜屼粨浣嶈鍒掞紝涓嶆敼 registry 鐪熷€笺€?    """
    phases: list[PipelinePhaseResult] = []
    decision_view: Optional[PipelineDecisionView] = None
    plan_view: Optional[PipelinePlanView] = None
    error_msg: Optional[str] = None
    status = "done"

    ts = req.timestamp or datetime.utcnow()

    # 鈹€鈹€ Phase 5锛氬垎鏋?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    t0 = time.perf_counter()
    try:
        analysis_result = _run_phase5(req, ts)
        phases.append(PipelinePhaseResult(
            phase="analysis",
            ok=True,
            duration_ms=(time.perf_counter() - t0) * 1000,
            detail={
                "signal_id": analysis_result.get("signal_id"),
                "direction": analysis_result.get("direction"),
            },
        ))
    except Exception as e:
        phases.append(PipelinePhaseResult(
            phase="analysis",
            ok=False,
            duration_ms=(time.perf_counter() - t0) * 1000,
            error=str(e),
        ))
        error_msg = f"Phase 5 failed: {e}"
        status = "partial"

    # 鈹€鈹€ Phase 6锛氫徊瑁?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    t0 = time.perf_counter()
    decision = None
    try:
        decision = _run_phase6(req, ts)
        phases.append(PipelinePhaseResult(
            phase="arbitration",
            ok=True,
            duration_ms=(time.perf_counter() - t0) * 1000,
            detail={
                "decision_id": decision.decision_id,
                "bias": decision.bias,
                "confidence": decision.confidence,
            },
        ))
        decision_view = PipelineDecisionView(
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            bias=decision.bias,
            confidence=decision.confidence,
            signal_count=decision.signal_count,
            rules_applied=list(decision.rules_applied) if decision.rules_applied else [],
            timestamp=decision.timestamp or ts,
        )
    except Exception as e:
        phases.append(PipelinePhaseResult(
            phase="arbitration",
            ok=False,
            duration_ms=(time.perf_counter() - t0) * 1000,
            error=str(e),
        ))
        error_msg = f"Phase 6 failed: {e}"
        status = "partial"

    # 鈹€鈹€ Phase 7锛氶鎺?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    t0 = time.perf_counter()
    plan = None
    if decision and decision.bias not in ("no_trade", "exit_bias"):
        try:
            plan = _run_phase7(req, decision, ts)
            plan_view = PipelinePlanView(
                plan_id=plan.plan_id,
                symbol=plan.symbol,
                direction=plan.direction,
                final_quantity=plan.final_quantity,
                veto_triggered=plan.veto_triggered,
                limit_checks=[
                    {"limit_name": lc.limit_name, "passed": lc.passed}
                    for lc in (plan.limit_checks or [])
                ],
            )
            phases.append(PipelinePhaseResult(
                phase="risk",
                ok=True,
                duration_ms=(time.perf_counter() - t0) * 1000,
                detail={
                    "plan_id": plan.plan_id,
                    "direction": plan.direction,
                },
            ))
        except Exception as e:
            phases.append(PipelinePhaseResult(
                phase="risk",
                ok=False,
                duration_ms=(time.perf_counter() - t0) * 1000,
                error=str(e),
            ))
            error_msg = f"Phase 7 failed: {e}"
            status = "partial"
    else:
        phases.append(PipelinePhaseResult(
            phase="risk",
            ok=True,
            duration_ms=(time.perf_counter() - t0) * 1000,
            detail={"skipped": True, "reason": f"bias={getattr(decision, 'bias', 'N/A')} 鈥?no trade"},
        ))

    _log_pipeline_feedback(user.id, req, phases, decision_view, plan_view)

    return PipelineRunFullResponse(
        ok=status == "done",
        task_id="immediate",
        status=status,
        symbol=req.symbol,
        phases=phases,
        decision=decision_view,
        plan=plan_view,
        error=error_msg,
    )


@router.post(
    "/run-live",
    response_model=LivePipelineResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def run_live_pipeline(
    req: LiveRunRequest,
    user: User = Depends(require_suggest),
) -> LivePipelineResponse:
    import asyncio

    result = await asyncio.to_thread(_run_live_pipeline_sync, req)
    _log_pipeline_feedback(
        user.id,
        PipelineRunFullRequest(
            symbol=req.symbol,
            direction=result["decision"]["bias_direction"],
            confidence=result["decision"]["confidence"],
            strength=result["decision"]["confidence"],
            regime=result["decision"]["regime"],
        ),
        [],
        None,
        None,
    )
    return LivePipelineResponse(
        ok=True,
        data=LiveDataSummaryView(**result["data"]),
        modules=[LiveModuleView(**item) for item in result["modules"]],
        decision=result["decision"],
        plan=result["plan"],
        suggestions=result["suggestions"],
        explanation=result["explanation"],
        watch_plan=result["watch_plan"],
        data_status=result["data_status"],
        execution=result["execution"],
        audit=result["audit"],
        feedback=result["feedback"],
    )


# 鈹€鈹€ Phase 5 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _run_phase5(req: PipelineRunFullRequest, ts: datetime) -> dict:
    """璋冪敤 Phase 5 鍒嗘瀽寮曟搸锛堝唴閮?import锛夈€?"""
    from apps.api.routers.analysis import _call_analysis_engine
    signal = _call_analysis_engine(req.symbol, {
        "direction": req.direction,
        "confidence": req.confidence,
        "score": req.strength,
    })
    signal_dir = signal.direction.value if hasattr(signal.direction, "value") else str(signal.direction)
    return {
        "signal_id": f"{signal.engine_name}-{signal.symbol}",
        "direction": signal_dir,
    }


# 鈹€鈹€ Phase 6 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _run_phase6(req: PipelineRunFullRequest, ts: datetime):
    """
    璋冪敤 Phase 6 ArbitrationEngine.arbitrate()銆?
    澶嶇敤 arbitration router 鐨勫唴閮ㄥ疄鐜帮紝涓嶉噸鍐欓€昏緫銆?    """
    from apps.api.routers.arbitration import _call_arbitration_engine
    from apps.dto.api.arbitration import ArbitrationRunRequest
    ar_req = ArbitrationRunRequest(
        symbol=req.symbol,
        direction=req.direction,
        confidence=req.confidence,
        strength=req.strength,
        regime=req.regime,
        timestamp=ts,
    )
    return _call_arbitration_engine(ar_req)


def _bias_to_risk_format(direction: str, arb_bias: str) -> str:
    """灏嗕徊瑁?bias 鎴?direction 鏄犲皠涓?RiskCalculateRequest 鏍煎紡銆?"""
    if arb_bias in ("long_bias", "short_bias", "hold_bias", "no_trade", "reduce_risk", "exit_bias"):
        return arb_bias
    # 浠?direction 鎺ㄥ
    dir_map = {"LONG": "long_bias", "SHORT": "short_bias", "FLAT": "no_trade"}
    return dir_map.get(direction.upper(), "no_trade")


# 鈹€鈹€ Phase 7 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _run_phase7(req: PipelineRunFullRequest, decision, ts: datetime):
    """
    璋冪敤 Phase 7 RiskEngine銆?
    澶嶇敤 risk router 鐨勫唴閮ㄥ疄鐜帮紝涓嶉噸鍐欓€昏緫銆?    杩斿洖 core PositionPlan锛岀敱璋冪敤鏂硅浆鎹负 PipelinePlanView銆?    """
    from apps.api.routers.risk import _call_risk_engine
    from apps.dto.api.risk import RiskCalculateRequest

    risk_bias = _bias_to_risk_format(req.direction, getattr(decision, "bias", ""))

    risk_req = RiskCalculateRequest(
        symbol=req.symbol,
        decision_id=decision.decision_id,
        bias=risk_bias,
        confidence=req.confidence,
        direction=getattr(getattr(decision, "direction", None), "value", None),
        target_direction=getattr(decision, "target_direction", None),
        risk_adjustment=getattr(decision, "risk_adjustment", 1.0),
        no_trade_reason=getattr(decision, "no_trade_reason", None),
        portfolio_value=100000.0,
        current_price=100.0,
        regime=req.regime,
        timestamp=ts,
    )
    plan = _call_risk_engine(risk_req)
    return plan


def _run_live_pipeline_sync(req: LiveRunRequest) -> dict:
    from core.data.live import LiveAnalysisOrchestrator

    orchestrator = LiveAnalysisOrchestrator(profile_id=req.profile_id)
    result = orchestrator.run_live_pipeline(
        symbol=req.symbol,
        timeframe=req.timeframe,
        market_type=req.market_type,
        lookback=req.lookback,
        start=req.start,
        end=req.end,
        news_limit=req.news_limit,
        profile_id=req.profile_id,
    )
    bars = result["bars"]
    decision = result["decision"]
    plan = result["plan"]
    decision_record = result["decision_record"]
    risk_audit = result["risk_audit"]
    execution_result = result["execution_result"]
    execution_record = result["execution_record"]
    feedbacks = result["feedbacks"]
    modules = [module.to_public() for module in result["modules"].values()]

    technical_regime = result["signals"]["technical"].regime
    regime_value = technical_regime.value if hasattr(technical_regime, "value") else str(technical_regime)
    bias_direction = "FLAT"
    if decision.bias == "long_bias":
        bias_direction = "LONG"
    elif decision.bias == "short_bias":
        bias_direction = "SHORT"
    plan_veto_reason = (plan.veto_reasons or [None])[0]
    failed_check = next((lc for lc in (plan.limit_checks or []) if not lc.passed), None)
    plan_veto_source = None
    plan_decision_gate_reason = None
    if plan.veto_triggered:
        if failed_check is not None:
            plan_veto_source = failed_check.limit_name
        elif plan_veto_reason and str(plan_veto_reason).startswith("sizing_zero_quantity"):
            plan_veto_source = "sizing"
            plan_decision_gate_reason = str(plan_veto_reason)
        elif plan_veto_reason and ("arbitration" in str(plan_veto_reason) or "no_trade" in str(plan_veto_reason)):
            plan_veto_source = "arbitration"
            plan_decision_gate_reason = str(plan_veto_reason)
        else:
            plan_veto_source = "decision_gate"
            plan_decision_gate_reason = str(plan_veto_reason) if plan_veto_reason else None

    return {
        "data": {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "market_type": req.market_type,
            "profile_id": result["profile"].profile_id,
            "lookback": req.lookback,
            "start": result["start"],
            "end": result["end"],
            "bar_count": len(bars),
            "intraday_bar_count": len(result["intraday_bars"]),
            "latest_timestamp": bars[-1].timestamp,
        },
        "modules": modules,
        "decision": {
            "decision_id": decision.decision_id,
            "symbol": decision.symbol,
            "bias": decision.bias,
            "bias_direction": bias_direction,
            "confidence": decision.confidence,
            "signal_count": decision.signal_count,
            "rules_applied": list(decision.rules_applied),
            "regime": regime_value,
        },
        "plan": {
            "plan_id": plan.plan_id,
            "symbol": plan.symbol,
            "direction": plan.direction.value if hasattr(plan.direction, "value") else str(plan.direction),
            "final_quantity": plan.final_quantity,
            "veto_triggered": plan.veto_triggered,
            "veto_reason": plan_veto_reason,
            "veto_source": plan_veto_source,
            "decision_gate_reason": plan_decision_gate_reason,
            "limit_checks": [
                {
                    "limit_name": lc.limit_name,
                    "passed": lc.passed,
                    "mode": lc.mode,
                    "raw_qty": lc.raw_qty,
                    "adjusted_qty": lc.actual_value,
                    "details": lc.details,
                }
                for lc in (plan.limit_checks or [])
            ],
        },
        "suggestions": result["suggestions"],
        "explanation": result["explanation"],
        "watch_plan": result["watch_plan"],
        "data_status": result["data_status"],
        "audit": {
            "decision_record_id": decision_record.audit_id,
            "risk_audit_id": risk_audit.audit_id,
            "execution_record_id": execution_record.audit_id if execution_record else None,
            "feedback_registry_appended": bool(feedbacks),
        },
        "execution": {
            "mode": "simulation",
            "status": (
                "complete"
                if execution_result and execution_result.report.is_complete
                else "skipped" if execution_result is None else "partial"
            ),
            "fill_count": len(execution_result.fills) if execution_result else 0,
            "total_filled_qty": float(execution_record.total_filled_qty) if execution_record else 0.0,
            "avg_execution_price": execution_record.avg_execution_price if execution_record else None,
            "execution_record_id": execution_record.audit_id if execution_record else None,
        },
        "feedback": {
            "count": len(feedbacks),
            "items": [
                {
                    "feedback_id": fb.feedback_id,
                    "feedback_type": fb.feedback_type.value if hasattr(fb.feedback_type, "value") else str(fb.feedback_type),
                    "severity": fb.severity,
                }
                for fb in feedbacks
            ],
        },
    }


# 鈹€鈹€ 瀹¤鏃ュ織 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _log_pipeline_feedback(
    user_id: str,
    req: PipelineRunFullRequest,
    phases: list,
    decision_view: Optional[PipelineDecisionView],
    plan_view: Optional[PipelinePlanView],
) -> None:
    try:
        from apps.auth import get_auth_service
        auth = get_auth_service()
        auth.log(
            user_id=user_id,
            action="POST /pipeline/run-full",
            resource="pipeline",
            detail={
                "symbol": req.symbol,
                "direction": req.direction,
                "phases": [(p.phase, p.ok) for p in phases],
                "decision_bias": decision_view.bias if decision_view else None,
                "plan_id": plan_view.plan_id if plan_view else None,
            },
            result="accepted",
        )
    except Exception as exc:
        logger.warning("Failed to append pipeline auth audit", exc_info=True)
