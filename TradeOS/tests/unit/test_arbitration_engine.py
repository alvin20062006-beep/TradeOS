"""
Test: Arbitration Engine (Integration)
=====================================

端到端集成测试：验证完整仲裁流程。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.arbitration import ArbitrationEngine
from core.schemas import (
    ChanSignal,
    Direction,
    MacroSignal,
    OrderFlowSignal,
    Regime,
    SentimentEvent,
    TechnicalSignal,
    TimeFrame,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def engine() -> ArbitrationEngine:
    return ArbitrationEngine()


@pytest.fixture
def ts() -> datetime:
    return datetime(2026, 4, 11, 6, 0, 0)


def tech_signal(ts: datetime, direction: Direction, confidence: float) -> TechnicalSignal:
    return TechnicalSignal(
        engine_name="technical",
        symbol="AAPL",
        timestamp=ts,
        direction=direction,
        confidence=confidence,
        regime=Regime.TRENDING_UP,
    )


def chan_signal(ts: datetime, direction: Direction, confidence: float) -> ChanSignal:
    return ChanSignal(
        engine_name="chan",
        symbol="AAPL",
        timestamp=ts,
        direction=direction,
        confidence=confidence,
        regime=Regime.TRENDING_UP,
    )


def of_signal(ts: datetime, imbalance: float) -> OrderFlowSignal:
    return OrderFlowSignal(
        symbol="AAPL",
        timestamp=ts,
        timeframe=TimeFrame.M5,
        book_imbalance=imbalance,
    )


def sent_signal(ts: datetime, composite: float) -> SentimentEvent:
    return SentimentEvent(
        symbol="AAPL",
        timestamp=ts,
        composite_sentiment=composite,
    )


def macro_signal(ts: datetime, risk_on: bool, confidence: float) -> MacroSignal:
    return MacroSignal(
        timestamp=ts,
        regime=Regime.TRENDING_UP,
        regime_confidence=confidence,
        risk_on=risk_on,
    )


# ── Basic Flow Tests ──────────────────────────────────────────


class TestArbitrationEngineBasic:
    def test_all_signals_long(self, engine: ArbitrationEngine, ts: datetime) -> None:
        bundle = engine.collector.collect(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.LONG, 0.8),
            chan=chan_signal(ts, Direction.LONG, 0.7),
            orderflow=of_signal(ts, 0.8),
            sentiment=sent_signal(ts, 0.7),
            macro=macro_signal(ts, True, 0.75),
        )
        assert bundle.signals_present == 5

    def test_no_signals_returns_no_trade(self, engine: ArbitrationEngine, ts: datetime) -> None:
        bundle = engine.collector.collect(symbol="AAPL", timestamp=ts)
        assert bundle.signals_present == 0

        decision = engine.arbitrate(symbol="AAPL", timestamp=ts)
        assert decision.bias == "no_trade"
        assert decision.signal_count == 0

    def test_single_long_signal_returns_long_bias(self, engine: ArbitrationEngine, ts: datetime) -> None:
        decision = engine.arbitrate(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.LONG, 0.8),
        )
        assert decision.bias in ("long_bias", "hold_bias")
        assert decision.confidence > 0

    def test_single_short_signal_returns_short_bias(self, engine: ArbitrationEngine, ts: datetime) -> None:
        decision = engine.arbitrate(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.SHORT, 0.8),
        )
        assert decision.bias in ("short_bias", "hold_bias")

    def test_missing_signals_handled(self, engine: ArbitrationEngine, ts: datetime) -> None:
        # 只有 2 个信号，其余为 None
        decision = engine.arbitrate(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.LONG, 0.8),
            sentiment=sent_signal(ts, 0.7),
        )
        assert decision.signal_count == 2
        assert decision.bias in ("long_bias", "hold_bias", "no_trade")

    def test_bias_values_valid(self, engine: ArbitrationEngine, ts: datetime) -> None:
        from core.arbitration.schemas import ARBITRATION_BIAS_OPTIONS

        for conf in [0.3, 0.5, 0.7, 0.9]:
            decision = engine.arbitrate(
                symbol="AAPL",
                timestamp=ts,
                technical=tech_signal(ts, Direction.LONG, conf),
            )
            assert decision.bias in ARBITRATION_BIAS_OPTIONS

    def test_scores_normalized(self, engine: ArbitrationEngine, ts: datetime) -> None:
        decision = engine.arbitrate(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.LONG, 0.9),
            chan=chan_signal(ts, Direction.LONG, 0.7),
        )
        total = decision.long_score + decision.short_score + decision.neutrality_score
        assert abs(total - 1.0) < 1e-6


class TestSignalCounting:
    def test_signals_present_count_correct(self, engine: ArbitrationEngine, ts: datetime) -> None:
        bundle = engine.collector.collect(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.LONG, 0.8),
            chan=chan_signal(ts, Direction.LONG, 0.7),
            # orderflow = None
            sentiment=sent_signal(ts, 0.6),
            macro=macro_signal(ts, True, 0.5),
            # fundamental = None
        )
        assert bundle.signals_present == 4


class TestLowLatency:
    def test_arbitration_latency_recorded(self, engine: ArbitrationEngine, ts: datetime) -> None:
        decision = engine.arbitrate(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.LONG, 0.8),
        )
        assert decision.arbitration_latency_ms >= 0

    def test_arbitration_fast(self, engine: ArbitrationEngine, ts: datetime) -> None:
        import time

        start = time.perf_counter()
        for _ in range(100):
            engine.arbitrate(
                symbol="AAPL",
                timestamp=ts,
                technical=tech_signal(ts, Direction.LONG, 0.8),
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        avg_ms = elapsed_ms / 100
        assert avg_ms < 100, f"Average arbitration too slow: {avg_ms:.2f}ms"


class TestRulesApplied:
    def test_rules_applied_field_populated(self, engine: ArbitrationEngine, ts: datetime) -> None:
        decision = engine.arbitrate(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.LONG, 0.8),
        )
        assert isinstance(decision.rules_applied, list)

    def test_rationale_field_populated(self, engine: ArbitrationEngine, ts: datetime) -> None:
        decision = engine.arbitrate(
            symbol="AAPL",
            timestamp=ts,
            technical=tech_signal(ts, Direction.LONG, 0.8),
            sentiment=sent_signal(ts, 0.7),
        )
        assert isinstance(decision.rationale, list)
        assert len(decision.rationale) >= 1
        for r in decision.rationale:
            assert hasattr(r, "signal_name")
            assert hasattr(r, "contribution")


class TestTimestampHandling:
    def test_custom_timestamp_used(self, engine: ArbitrationEngine, ts: datetime) -> None:
        decision = engine.arbitrate(symbol="AAPL", timestamp=ts)
        assert decision.timestamp == ts
