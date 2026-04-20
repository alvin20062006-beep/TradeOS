"""Schemas used by the arbitration layer."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.analysis.fundamental.report import FundamentalReport
from core.schemas import (
    ArbitrationDecision,
    ChanSignal,
    ConflictRecord,
    DecisionRationale,
    Direction,
    MacroSignal,
    OrderFlowSignal,
    Regime,
    SentimentEvent,
    TechnicalSignal,
)


class DirectionalSignal(BaseModel):
    """Normalized directional view consumed by scoring and rule chains."""

    engine_name: str
    direction: Direction
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    regime: Optional[Regime] = None
    weight: float = 1.0
    raw_signal: Optional[BaseModel] = None

    def score(self) -> float:
        sign = 1 if self.direction == Direction.LONG else -1 if self.direction == Direction.SHORT else 0
        return sign * self.confidence * self.weight


class SignalBundle(BaseModel):
    """Collected six-module snapshot passed into arbitration."""

    timestamp: datetime
    symbol: str
    technical: Optional[TechnicalSignal] = None
    chan: Optional[ChanSignal] = None
    orderflow: Optional[OrderFlowSignal] = None
    sentiment: Optional[SentimentEvent] = None
    macro: Optional[MacroSignal] = None
    fundamental: Optional[FundamentalReport] = None
    collection_latency_ms: float = 0.0

    @property
    def signals_present(self) -> int:
        return sum(
            1
            for signal in (
                self.technical,
                self.chan,
                self.orderflow,
                self.sentiment,
                self.macro,
            )
            if signal is not None
        )


ARBITRATION_BIAS_OPTIONS = [
    "no_trade",
    "long_bias",
    "short_bias",
    "hold_bias",
    "reduce_risk",
    "exit_bias",
]


class SignalScore(BaseModel):
    """Scored directional signal after arbitration rules."""

    engine_name: str
    direction: Direction
    raw_confidence: float
    adjusted_confidence: float
    weight: float
    contribution: float
    regime: Optional[Regime] = None
    rule_adjustments: list[str] = Field(default_factory=list)


class _StrategySignalSource(BaseModel):
    """Phase 9 bridge object converted into the Phase 6 normalized signal format."""

    proposal_id: str
    strategy_id: str
    aggregate_direction: str
    aggregate_strength: float = Field(0.0, ge=0.0, le=1.0)
    aggregate_confidence: float = Field(0.0, ge=0.0, le=1.0)
    portfolio_weight: float = Field(0.0, ge=0.0, le=1.0)

    def to_directional(self) -> DirectionalSignal:
        direction = {
            "LONG": Direction.LONG,
            "SHORT": Direction.SHORT,
            "FLAT": Direction.FLAT,
        }.get(self.aggregate_direction.upper(), Direction.FLAT)
        return DirectionalSignal(
            engine_name=f"strategy_pool:{self.strategy_id}",
            direction=direction,
            confidence=self.aggregate_confidence,
            weight=self.portfolio_weight if self.portfolio_weight > 0 else 1.0,
        )
