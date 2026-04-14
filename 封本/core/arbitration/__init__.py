"""
Arbitration Layer
================

Unified decision arbitration for the six analysis engines.

Inputs:  TechnicalSignal, ChanSignal, OrderFlowSignal,
         SentimentEvent, MacroSignal, FundamentalReport
Output:  ArbitrationDecision

Phase 6 of the ai-trading-tool project.
"""

from __future__ import annotations

from core.arbitration.schemas import (
    ArbitrationDecision,
    ConflictRecord,
    DecisionRationale,
    SignalBundle,
)

from core.arbitration.conflict_resolver import ConflictResolver
from core.arbitration.decision_maker import DecisionMaker
from core.arbitration.engine import ArbitrationEngine
from core.arbitration.signal_collector import SignalCollector

__all__ = [
    "ArbitrationEngine",
    "ArbitrationDecision",
    "SignalBundle",
    "ConflictRecord",
    "DecisionRationale",
    "SignalCollector",
    "ConflictResolver",
    "DecisionMaker",
]
