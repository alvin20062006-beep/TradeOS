"""Execution-layer models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.execution.enums import (
    EngineStatus,
    ExecutionStatus,
    LiquiditySide,
    OrderType,
    RiskFlagType,
    RiskSeverity,
    Side,
    TimeInForce,
    Urgency,
)


class StatusTransition(BaseModel):
    from_status: ExecutionStatus
    to_status: ExecutionStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionRiskFlag(BaseModel):
    flag_type: RiskFlagType
    severity: RiskSeverity
    threshold_value: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None
    description: Optional[str] = None
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    source: Optional[str] = None


class ExecutionIntent(BaseModel):
    intent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str
    decision_id: Optional[str] = None
    symbol: str
    venue: Optional[str] = None
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    expire_at: Optional[datetime] = None
    execution_algo: Optional[str] = None
    urgency: Urgency = Urgency.NORMAL
    max_slippage_bps: Optional[int] = None
    participation_rate_limit: Optional[Decimal] = None
    risk_flags: list[ExecutionRiskFlag] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def has_blocking_risk(self) -> bool:
        return any(flag.severity == RiskSeverity.BLOCK for flag in self.risk_flags)


class ExecutionReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent_id: str
    order_id: Optional[str] = None
    status: ExecutionStatus
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    last_update_at: datetime = Field(default_factory=datetime.utcnow)
    filled_qty: Decimal = Decimal("0")
    remaining_qty: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    total_fees: Decimal = Decimal("0")
    slippage_estimate_bps: Optional[int] = None
    venue_latency_ms: Optional[int] = None
    venue: Optional[str] = None
    raw_reference: Optional[str] = None
    reject_reason: Optional[str] = None
    reject_code: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            ExecutionStatus.FILLED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.EXPIRED,
        }

    @property
    def is_complete(self) -> bool:
        return self.status == ExecutionStatus.FILLED


class FillRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    intent_id: str
    symbol: str
    side: Side
    filled_qty: Decimal
    fill_price: Decimal
    fees: Decimal = Decimal("0")
    venue: Optional[str] = None
    trade_id: Optional[str] = None
    liquidity_side: Optional[LiquiditySide] = None
    filled_at: datetime
    raw_reference: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent_id: str
    order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal]
    stop_price: Optional[Decimal]
    time_in_force: TimeInForce
    status_history: list[StatusTransition] = Field(default_factory=list)
    current_status: ExecutionStatus = ExecutionStatus.PENDING
    fills: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def add_transition(
        self,
        to_status: ExecutionStatus,
        reason: Optional[str] = None,
    ) -> StatusTransition:
        transition = StatusTransition(
            from_status=self.current_status,
            to_status=to_status,
            reason=reason,
        )
        self.status_history.append(transition)
        self.current_status = to_status
        self.updated_at = datetime.utcnow()
        return transition


class PositionState(BaseModel):
    position_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    venue: Optional[str] = None
    net_qty: Decimal = Decimal("0")
    avg_cost: Decimal = Decimal("0")
    total_traded_qty: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    exposure: Decimal = Decimal("0")
    margin_used: Optional[Decimal] = None
    opened_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source_orders: list[str] = Field(default_factory=list)
    source_fills: list[str] = Field(default_factory=list)

    @property
    def is_long(self) -> bool:
        return self.net_qty > 0

    @property
    def is_short(self) -> bool:
        return self.net_qty < 0

    @property
    def is_flat(self) -> bool:
        return self.net_qty == 0


class OrderSnapshot(BaseModel):
    order_id: str
    symbol: str
    venue: Optional[str] = None
    side: Side
    order_type: OrderType
    status: str
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    remaining_quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExecutionResult(BaseModel):
    intent: ExecutionIntent
    report: ExecutionReport
    order: Optional[OrderRecord] = None
    fills: list[FillRecord] = Field(default_factory=list)
    position: Optional[PositionState] = None
    venue: Optional[str] = None
    mode: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeReport(BaseModel):
    status: str
    mode: str
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    adapters: dict[str, str] = Field(default_factory=dict)
    total_orders: int = 0
    total_fills: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None
