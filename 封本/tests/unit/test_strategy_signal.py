"""
tests/unit/test_strategy_signal.py
================================
Unit tests for strategy signals and intents.
"""

import pytest
import pandas as pd
from datetime import datetime

from core.research.strategy.signal import (
    SignalDirection,
    StrategySignal,
    StrategyIntent,
)


class TestStrategySignal:
    def test_long_signal(self):
        sig = StrategySignal(
            asset_id="AAPL",
            timestamp=datetime(2024, 1, 1),
            direction=SignalDirection.LONG,
            confidence=0.8,
        )
        assert sig.direction == SignalDirection.LONG
        assert sig.confidence == 0.8
        w = sig.to_weights()
        assert w["AAPL"] == 1.0

    def test_short_signal(self):
        sig = StrategySignal(
            asset_id="AAPL",
            timestamp=datetime(2024, 1, 1),
            direction=SignalDirection.SHORT,
            confidence=0.5,
        )
        w = sig.to_weights()
        assert w["AAPL"] == -1.0  # normalized

    def test_neutral_signal(self):
        sig = StrategySignal(
            asset_id="AAPL",
            timestamp=datetime(2024, 1, 1),
            direction=SignalDirection.NEUTRAL,
        )
        w = sig.to_weights()
        assert w["AAPL"] == 0.0

    def test_confidence_range(self):
        with pytest.raises(ValueError, match="confidence must be in"):
            StrategySignal(
                asset_id="AAPL",
                timestamp=datetime(2024, 1, 1),
                direction=SignalDirection.LONG,
                confidence=1.5,
            )

    def test_direction_from_string(self):
        sig = StrategySignal(
            asset_id="AAPL",
            timestamp=datetime(2024, 1, 1),
            direction="long",  # str, not enum
            confidence=0.7,
        )
        assert sig.direction == SignalDirection.LONG

    def test_to_weights_normalizes(self):
        sig = StrategySignal(
            asset_id="AAPL",
            timestamp=datetime(2024, 1, 1),
            direction=SignalDirection.LONG,
            confidence=0.5,
        )
        w = sig.to_weights()
        assert abs(w.sum() - 1.0) < 1e-9


class TestStrategyIntent:
    def test_weights_normalized(self):
        intent = StrategyIntent(
            timestamp=datetime(2024, 1, 1),
            weights=pd.Series([60.0, 40.0], index=["AAPL", "GOOG"]),
        )
        w = intent.to_weights_series()
        assert abs(w.sum() - 1.0) < 1e-9
        assert w["AAPL"] == 0.6

    def test_empty_weights_rejected(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            StrategyIntent(
                timestamp=datetime(2024, 1, 1),
                weights=pd.Series(dtype=float),
            )

    def test_as_dict(self):
        sig = StrategySignal(
            asset_id="AAPL",
            timestamp=datetime(2024, 1, 1),
            direction=SignalDirection.LONG,
        )
        intent = StrategyIntent(
            timestamp=datetime(2024, 1, 1),
            weights=pd.Series([1.0], index=["AAPL"]),
            signals=[sig],
            metadata={"strategy": "test"},
        )
        d = intent.as_dict()
        assert d["weights"] == {"AAPL": 1.0}
        assert d["n_signals"] == 1
        assert d["metadata"]["strategy"] == "test"
