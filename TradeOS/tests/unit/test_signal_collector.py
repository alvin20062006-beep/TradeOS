"""
Test: Signal Collector
=====================

验证信号收集、时间对齐、缺失处理。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.arbitration import SignalCollector
from core.schemas import (
    Direction,
    MacroSignal,
    OrderFlowSignal,
    Regime,
    SentimentEvent,
    TechnicalSignal,
    TimeFrame,
)


class TestSignalCollector:
    def setup_method(self) -> None:
        self.collector = SignalCollector()

    def test_collect_empty_returns_bundle(self) -> None:
        bundle = self.collector.collect(symbol="AAPL")
        assert bundle.symbol == "AAPL"
        assert bundle.signals_present == 0

    def test_collect_all_signals(self) -> None:
        ts = datetime(2026, 4, 11)
        bundle = self.collector.collect(
            symbol="AAPL",
            timestamp=ts,
            technical=TechnicalSignal(
                engine_name="technical", symbol="AAPL", timestamp=ts,
                direction=Direction.LONG, confidence=0.8, regime=Regime.TRENDING_UP,
            ),
            sentiment=SentimentEvent(symbol="AAPL", timestamp=ts, composite_sentiment=0.7),
        )
        assert bundle.signals_present == 2
        assert bundle.technical is not None
        assert bundle.sentiment is not None

    def test_timestamp_default_now(self) -> None:
        before = datetime.utcnow()
        bundle = self.collector.collect(symbol="AAPL")
        after = datetime.utcnow()
        assert before <= bundle.timestamp <= after

    def test_timestamp_custom_used(self) -> None:
        ts = datetime(2026, 1, 1, 12, 0, 0)
        bundle = self.collector.collect(symbol="AAPL", timestamp=ts)
        assert bundle.timestamp == ts

    def test_missing_signals_optional(self) -> None:
        bundle = self.collector.collect(
            symbol="TSLA",
            technical=TechnicalSignal(
                engine_name="technical", symbol="TSLA", timestamp=datetime.utcnow(),
                direction=Direction.LONG, confidence=0.6, regime=Regime.RANGING,
            ),
        )
        assert bundle.chan is None
        assert bundle.orderflow is None
        assert bundle.sentiment is None
        assert bundle.macro is None
        assert bundle.signals_present == 1

    def test_collection_latency_recorded(self) -> None:
        bundle = self.collector.collect(symbol="AAPL")
        assert bundle.collection_latency_ms >= 0
