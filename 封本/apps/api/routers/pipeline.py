"""
apps/api/routers/pipeline.py — 全链路编排 API 端点

POST /pipeline/run-full：串联 Phase 5 → 6 → 7
    GET /pipeline/status/{task_id}：查询 pipeline 状态

约束：
- 纯 orchestration，不重写任何阶段逻辑
- 串联现有公开 API/方法
- 不暴露核心内部对象
"""

from __future__ import annotations

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
    全链路编排（Phase 5 → 6 → 7）。

    串联现有公开方法，不重写阶段逻辑。
    suggestion-only：只输出决策和仓位计划，不改 registry 真值。
    """
    phases: list[PipelinePhaseResult] = []
    decision_view: Optional[PipelineDecisionView] = None
    plan_view: Optional[PipelinePlanView] = None
    error_msg: Optional[str] = None
    status = "done"

    ts = req.timestamp or datetime.utcnow()

    # ── Phase 5：分析 ──────────────────────────────────
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

    # ── Phase 6：仲裁 ──────────────────────────────────
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

    # ── Phase 7：风控 ──────────────────────────────────
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
            detail={"skipped": True, "reason": f"bias={getattr(decision, 'bias', 'N/A')} — no trade"},
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
        audit=result["audit"],
        feedback=result["feedback"],
    )


# ── Phase 5 ─────────────────────────────────────────────────

def _run_phase5(req: PipelineRunFullRequest, ts: datetime) -> dict:
    """调用 Phase 5 分析引擎（内部 import）。"""
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


# ── Phase 6 ─────────────────────────────────────────────────

def _run_phase6(req: PipelineRunFullRequest, ts: datetime):
    """
    调用 Phase 6 ArbitrationEngine.arbitrate()。

    复用 arbitration router 的内部实现，不重写逻辑。
    """
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
    """将仲裁 bias 或 direction 映射为 RiskCalculateRequest 格式。"""
    if arb_bias in ("long_bias", "short_bias", "hold_bias", "no_trade"):
        return arb_bias
    # 从 direction 推导
    dir_map = {"LONG": "long_bias", "SHORT": "short_bias", "FLAT": "no_trade"}
    return dir_map.get(direction.upper(), "no_trade")


# ── Phase 7 ─────────────────────────────────────────────────

def _run_phase7(req: PipelineRunFullRequest, decision, ts: datetime):
    """
    调用 Phase 7 RiskEngine。

    复用 risk router 的内部实现，不重写逻辑。
    返回 core PositionPlan，由调用方转换为 PipelinePlanView。
    """
    from apps.api.routers.risk import _call_risk_engine
    from apps.dto.api.risk import RiskCalculateRequest

    risk_bias = _bias_to_risk_format(req.direction, getattr(decision, "bias", ""))

    risk_req = RiskCalculateRequest(
        symbol=req.symbol,
        decision_id=decision.decision_id,
        bias=risk_bias,
        confidence=req.confidence,
        portfolio_value=100000.0,
        current_price=100.0,
        regime=req.regime,
        timestamp=ts,
    )
    plan = _call_risk_engine(risk_req)
    return plan


def _run_live_pipeline_sync(req: LiveRunRequest) -> dict:
    from core.data.live import LiveAnalysisOrchestrator

    orchestrator = LiveAnalysisOrchestrator()
    result = orchestrator.run_live_pipeline(
        symbol=req.symbol,
        timeframe=req.timeframe,
        lookback=req.lookback,
        start=req.start,
        end=req.end,
        news_limit=req.news_limit,
    )
    bars = result["bars"]
    decision = result["decision"]
    plan = result["plan"]
    decision_record = result["decision_record"]
    risk_audit = result["risk_audit"]
    feedbacks = result["feedbacks"]
    modules = [module.to_public() for module in result["modules"].values()]

    technical_regime = result["signals"]["technical"].regime
    regime_value = technical_regime.value if hasattr(technical_regime, "value") else str(technical_regime)
    bias_direction = "FLAT"
    if decision.bias == "long_bias":
        bias_direction = "LONG"
    elif decision.bias == "short_bias":
        bias_direction = "SHORT"

    return {
        "data": {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
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
            "limit_checks": [
                {
                    "limit_name": lc.limit_name,
                    "passed": lc.passed,
                    "mode": lc.mode,
                }
                for lc in (plan.limit_checks or [])
            ],
        },
        "audit": {
            "decision_record_id": decision_record.audit_id,
            "risk_audit_id": risk_audit.audit_id,
            "feedback_registry_appended": bool(feedbacks),
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


# ── 审计日志 ───────────────────────────────────────────────

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
    except Exception:
        pass
