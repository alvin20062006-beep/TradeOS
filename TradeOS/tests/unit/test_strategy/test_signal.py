"""
test_signal.py
=============
Unit tests for StrategySignal and StrategyIntent.
"""

import pytest
import pandas as pd
from datetime import datetime

from core.research.strategy.signal import SignalDirection, StrategySignal, StrategyIntent


class TestSignalDirection:
    def test_enum_values(self):
        assert SignalDirection.LONG.value == "long"
        assert SignalDirection.SHORT.value == "short"
        assert SignalDirection.NEUTRAL.value == "neutral"


class TestStrategySignal:
    def test_single_asset_long(self):
        sig = StrategySignal(
            asset_id="AAPL",
            timestamp=datetime(2024, 1, 1),
            direction=SignalDirection.LONG,
            confidence=0.8,
        )
        assert sig.direction == SignalDirection.LONG
        w = sig.to_weights()
        assert w["AAPL"] == pytest.approx(1.0)

    def test_single_asset_short(self):
        sig = StrategySignal(
            asset_id="AAPL",
            timestamp=datetime(2024, 1, 1),
            direction=SignalDirection.SHORT,
            confidence=0.5,
        )
        w = sig.to_weights()
        assert w["AAPL"] == pytest.approx(-1.0)

    def test_confidence_bounds(self):
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
            direction="long",
            confidence=0.7,
        )
        assert sig.direction == SignalDirection.LONG

    def test_from_alpha_long(self):
        alpha = pd.Series({"A": 0.1, "B": 0.05, "C": 0.08})
        sig = StrategySignal.from_alpha(alpha, strategy_id="test_alpha")
        assert sig.direction == SignalDirection.LONG
        assert 0.0 <= sig.confidence <= 1.0
        assert sig.weights is not None

    def test_from_alpha_short(self):
        alpha = pd.Series({"A": -0.1, "B": -0.05, "C": -0.08})
        sig = StrategySignal.from_alpha(alpha, strategy_id="test_alpha")
        assert sig.direction == SignalDirection.SHORT

    def test_from_alpha_neutral(self):
        alpha = pd.Series({"A": 0.0, "B": 0.0, "C": 0.0})
        sig = StrategySignal.from_alpha(alpha, strategy_id="test_alpha")
        assert sig.direction == SignalDirection.NEUTRAL

    def test_weights_normalize(self):
        alpha = pd.Series({"A": 3.0, "B": 2.0, "C": 1.0})
        sig = StrategySignal.from_alpha(alpha)
        total = float(sig.weights.abs().sum())
        assert total == pytest.approx(1.0, rel=1e-9)

    def test_multi_asset_weights_preserved(self):
        weights = pd.Series({"A": 0.6, "B": 0.4})
        sig = StrategySignal(
            timestamp=datetime(2024, 1, 1),
            direction=SignalDirection.LONG,
            confidence=0.8,
            weights=weights,
        )
        got = sig.to_weights()
        assert got.abs().sum() == pytest.approx(1.0, rel=1e-9)


class TestStrategyIntent:
    def test_weights_normalized(self):
        intent = StrategyIntent(
            timestamp=datetime(2024, 1, 1),
            weights=pd.Series([60.0, 40.0], index=["AAPL", "GOOG"]),
        )
        w = intent.to_weights_series()
        assert abs(w.sum() - 1.0) < 1e-9
        assert w["AAPL"] == pytest.approx(0.6)

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
