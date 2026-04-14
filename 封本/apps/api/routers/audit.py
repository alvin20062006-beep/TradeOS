"""Audit query APIs backed by real append-only stores."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from apps.auth import User, require_read, require_task
from apps.dto.api.audit import (
    AuditQueryParams,
    AuditQueryResponse,
    DecisionRecordView,
    FeedbackScanRequest,
    FeedbackScanResponse,
    FeedbackScanResult,
    FeedbackView,
    RiskAuditView,
)
from apps.dto.api.common import ErrorResponse
from core.audit.closed_loop import DecisionRegistry, FeedbackRegistry, RiskAuditRegistry

router = APIRouter(prefix="/audit", tags=["Audit"])

_task_store: dict[str, dict] = {}


@router.get(
    "/decisions",
    response_model=AuditQueryResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def query_decisions(
    params: AuditQueryParams = Depends(),
    user: User = Depends(require_read),
) -> AuditQueryResponse:
    records = DecisionRegistry().read_all(symbol=params.symbol, since=params.since)
    total = len(records)
    page = records[params.offset: params.offset + params.limit]
    items = [
        DecisionRecordView(
            decision_id=record.decision_id,
            symbol=record.symbol,
            timestamp=record.timestamp,
            bias=record.bias,
            confidence=record.final_confidence,
            signal_count=len(record.input_signals),
            rules_applied=[],
            audit_id=record.audit_id,
            source="decision_registry",
        )
        for record in page
    ]
    return AuditQueryResponse(
        ok=True,
        items=items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_more=(params.offset + params.limit) < total,
    )


@router.get(
    "/risk",
    response_model=AuditQueryResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def query_risk_audits(
    params: AuditQueryParams = Depends(),
    user: User = Depends(require_read),
) -> AuditQueryResponse:
    records = RiskAuditRegistry().read_all(symbol=params.symbol, since=params.since)
    total = len(records)
    page = records[params.offset: params.offset + params.limit]
    items = [
        RiskAuditView(
            plan_id=record.position_plan_id,
            symbol=record.symbol,
            timestamp=record.timestamp,
            final_quantity=record.final_quantity,
            veto_triggered=record.veto_triggered,
            limit_checks=[
                {
                    "filter_name": item.filter_name,
                    "passed": item.passed,
                    "mode": item.mode,
                    "raw_qty": item.raw_qty,
                    "adjusted_qty": item.adjusted_qty,
                    "reason": item.details,
                }
                for item in record.filter_results
            ],
            audit_id=record.audit_id,
            source="risk_registry",
        )
        for record in page
    ]
    return AuditQueryResponse(
        ok=True,
        items=items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_more=(params.offset + params.limit) < total,
    )


@router.get(
    "/feedback",
    response_model=AuditQueryResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def query_feedback(
    params: AuditQueryParams = Depends(),
    user: User = Depends(require_read),
) -> AuditQueryResponse:
    records = FeedbackRegistry().read_all(since=params.since)
    if params.symbol:
        records = [record for record in records if record.symbol == params.symbol]
    records.sort(key=lambda item: item.timestamp, reverse=True)
    total = len(records)
    page = records[params.offset: params.offset + params.limit]
    items = [
        FeedbackView(
            feedback_id=record.feedback_id,
            feedback_type=record.feedback_type.value,
            severity=record.severity,
            description=record.suggested_action,
            symbol=record.symbol,
            decision_id=record.source_audit_ids[0] if record.source_audit_ids else None,
            created_at=record.timestamp,
            metadata={
                "metric_name": record.metric_name,
                "metric_value": record.metric_value,
                "threshold_breach": record.threshold_breach,
                "status": record.status.value,
            },
        )
        for record in page
    ]
    return AuditQueryResponse(
        ok=True,
        items=items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_more=(params.offset + params.limit) < total,
    )


@router.post(
    "/feedback/tasks",
    response_model=FeedbackScanResponse,
    status_code=202,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def submit_feedback_scan_task(
    req: FeedbackScanRequest,
    user: User = Depends(require_task),
) -> FeedbackScanResponse:
    feedbacks = _run_feedback_scan(req)
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    _task_store[task_id] = {
        "task_id": task_id,
        "status": "done",
        "feedbacks": feedbacks,
        "feedback_count": len(feedbacks),
        "summary": f"Scanned {len(feedbacks)} feedback items",
        "error": None,
        "started_at": datetime.utcnow(),
        "completed_at": datetime.utcnow(),
    }
    return FeedbackScanResponse(
        ok=True,
        task_id=task_id,
        status="accepted",
        message=f"Feedback scan task submitted (task_id={task_id}). Use GET /audit/feedback/tasks/{task_id} to poll result.",
        submitted_at=datetime.utcnow(),
    )


@router.get(
    "/feedback/tasks/{task_id}",
    response_model=FeedbackScanResult,
    responses={404: {"model": ErrorResponse}},
)
async def get_feedback_task_status(
    task_id: str,
    user: User = Depends(require_read),
) -> FeedbackScanResult:
    task = _task_store.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "task_not_found", "message": f"Task {task_id} not found"},
        )
    return FeedbackScanResult(**task)


def _run_feedback_scan(req: FeedbackScanRequest) -> list[dict]:
    records = FeedbackRegistry().read_all(since=req.since)
    if req.symbol:
        records = [record for record in records if record.symbol == req.symbol]
    if req.feedback_type and req.feedback_type != "all":
        records = [record for record in records if record.feedback_type.value == req.feedback_type]
    records.sort(key=lambda item: item.timestamp, reverse=True)
    return [
        {
            "feedback_id": record.feedback_id,
            "feedback_type": record.feedback_type.value,
            "severity": record.severity,
            "description": record.suggested_action,
            "symbol": record.symbol,
            "decision_id": record.source_audit_ids[0] if record.source_audit_ids else None,
            "created_at": record.timestamp,
            "metadata": {
                "metric_name": record.metric_name,
                "metric_value": record.metric_value,
                "threshold_breach": record.threshold_breach,
                "status": record.status.value,
            },
        }
        for record in records
    ]
