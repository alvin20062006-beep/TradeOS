"""
Test: Conflict Resolver
======================

验证方向冲突检测、置信度裁决、hold_bias 降级。
独立测试：ConflictResolver 是 DirectionConflictRule 的包装，
在 engine 规则链之外直接调用时应正确工作。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.arbitration.conflict_resolver import ConflictResolver
from core.arbitration.schemas import (
    ArbitrationDecision,
    SignalBundle,
    SignalScore,
)
from core.schemas import Direction, Regime


def _make_bundle(ts: datetime) -> SignalBundle:
    return SignalBundle(timestamp=ts, symbol="AAPL")


def _make_scores(
    entries: list[dict],
) -> list[SignalScore]:
    """Helper: [(engine, direction, raw)]"""
    return [
        SignalScore(
            engine_name=e["engine"],
            direction=e["direction"],
            raw_confidence=e["raw"],
            adjusted_confidence=e.get("adj", e["raw"]),
            weight=e.get("weight", 1.0),
            contribution=e.get("contrib", e["raw"] if e["direction"] == Direction.LONG else -e["raw"]),
            regime=e.get("regime"),
            rule_adjustments=[],
        )
        for e in entries
    ]


class TestConflictResolver:
    def setup_method(self) -> None:
        self.resolver = ConflictResolver()

    def test_no_conflict_returns_empty(self) -> None:
        ts = datetime.utcnow()
        bundle = _make_bundle(ts)
        decision = ArbitrationDecision(
            decision_id="test-1", timestamp=ts, symbol="AAPL",
            bias="long_bias", confidence=0.8,
            long_score=0.8, short_score=0.0,
            neutrality_score=0.0,
        )
        # 仅有同向信号，无冲突
        scores = _make_scores([
            {"engine": "technical", "direction": Direction.LONG, "raw": 0.8},
            {"engine": "chan", "direction": Direction.LONG, "raw": 0.7},
        ])
        new = self.resolver.resolve(bundle, scores, decision)
        assert len(new) == 0

    def test_conflict_detected_high_confidence_wins(self) -> None:
        ts = datetime.utcnow()
        bundle = _make_bundle(ts)
        decision = ArbitrationDecision(
            decision_id="test-2", timestamp=ts, symbol="AAPL",
            bias="long_bias", confidence=0.8,
            long_score=0.0, short_score=0.0,
            neutrality_score=0.0,
        )
        # 正贡献 LONG + 正贡献 SHORT → 冲突
        scores = _make_scores([
            {"engine": "technical", "direction": Direction.LONG, "raw": 0.9,
             "contrib": 0.9},
            {"engine": "sentiment", "direction": Direction.SHORT, "raw": 0.6,
             "contrib": -0.6},
        ])
        self.resolver.resolve(bundle, scores, decision)
        assert len(decision.conflicts) >= 1

    def test_conflict_near_equal_triggers_hold_bias(self) -> None:
        ts = datetime.utcnow()
        bundle = _make_bundle(ts)
        decision = ArbitrationDecision(
            decision_id="test-3", timestamp=ts, symbol="AAPL",
            bias="long_bias", confidence=0.8,
            long_score=0.0, short_score=0.0,
            neutrality_score=0.0,
        )
        # 置信度差 0.05 < 0.1 阈值 → hold_bias
        scores = _make_scores([
            {"engine": "technical", "direction": Direction.LONG, "raw": 0.7,
             "contrib": 0.7},
            {"engine": "sentiment", "direction": Direction.SHORT, "raw": 0.65,
             "contrib": -0.65},
        ])
        self.resolver.resolve(bundle, scores, decision)
        assert decision.bias == "hold_bias"

    def test_conflict_record_fields_populated(self) -> None:
        ts = datetime.utcnow()
        bundle = _make_bundle(ts)
        decision = ArbitrationDecision(
            decision_id="test-4", timestamp=ts, symbol="AAPL",
            bias="long_bias", confidence=0.8,
            long_score=0.0, short_score=0.0,
            neutrality_score=0.0,
        )
        scores = _make_scores([
            {"engine": "technical", "direction": Direction.LONG, "raw": 0.9,
             "contrib": 0.9},
            {"engine": "orderflow", "direction": Direction.SHORT, "raw": 0.6,
             "contrib": -0.6},
        ])
        self.resolver.resolve(bundle, scores, decision)
        assert len(decision.conflicts) >= 1
        rec = decision.conflicts[-1]
        assert rec.signal_a != ""
        assert rec.signal_b != ""
        assert rec.resolution != ""
        assert rec.rule_applied == "direction_conflict"
