"""
test_base.py
============
Unit tests for StrategyBase and concrete strategy implementations.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from core.research.strategy.base import (
    StrategyBase,
    MomentumStrategy,
    MeanReversionStrategy,
    EqualWeightStrategy,
)
from core.research.strategy.signal import SignalDirection


class DummyStrategy(StrategyBase):
    """Concrete implementation for testing (matches pre-existing test)."""

    def __init__(self, name="test", long_only=True):
        super().__init__(name=name, description="Test strategy")
        self.long_only = long_only

    def generate_weights(self, timestamp, features):
        n = len(features)
        w = pd.Series(1.0 / n, index=features.index)
        if not self.long_only:
            half = n // 2
            idx = features.index[:half]
            w.loc[idx] = -w.loc[idx]
        return w


class TestStrategyBase:
    def test_repr(self):
        s = DummyStrategy(name="dummy")
        assert "DummyStrategy" in repr(s)
        assert "dummy" in repr(s)

    def test_generate_weights_equal_weight(self):
        s = DummyStrategy()
        features = pd.DataFrame(
            {"feat1": [1, 2, 3]},
            index=["AAPL", "GOOG", "MSFT"],
        )
        w = s.generate_weights(datetime.now(), features)
        assert w.sum() == pytest.approx(1.0)
        assert all(w > 0)

    def test_generate_weights_with_shorts(self):
        s = DummyStrategy(long_only=False)
        features = pd.DataFrame(
            {"feat1": [1, 2, 3, 4]},
            index=["A", "B", "C", "D"],
        )
        w = s.generate_weights(datetime.now(), features)
        assert w.sum() == pytest.approx(0.0)
        assert w["A"] < 0
        assert w["D"] > 0

    def test_fit_sets_fitted(self):
        s = DummyStrategy()
        assert not s.is_fitted()
        s.fit(pd.DataFrame())
        assert s.is_fitted()

    def test_signals_to_intent(self):
        from core.research.strategy.signal import StrategySignal
        s = DummyStrategy()
        signals = [
            StrategySignal(
                asset_id="AAPL",
                timestamp=datetime(2024, 1, 1),
                direction=SignalDirection.LONG,
                confidence=0.8,
            ),
            StrategySignal(
                asset_id="GOOG",
                timestamp=datetime(2024, 1, 1),
                direction=SignalDirection.SHORT,
                confidence=0.5,
            ),
        ]
        intent = s.signals_to_intent(signals, datetime(2024, 1, 1))
        assert set(intent.weights.index) == {"AAPL", "GOOG"}
        assert intent.weights["AAPL"] > 0
        assert intent.weights["GOOG"] < 0

    def test_generate_weights_series(self):
        s = DummyStrategy()
        dates = pd.date_range("2024-01-01", periods=3, freq="D")
        features_by_date = {
            d: pd.DataFrame({"f": [1.0, 2.0]}, index=["AAPL", "GOOG"])
            for d in dates
        }
        df = s.generate_weights_series(dates, features_by_date)
        assert df.shape == (3, 2)

    def test_abstract_method_required(self):
        class BadStrategy(StrategyBase):
            pass

        with pytest.raises(TypeError, match="abstract"):
            BadStrategy()


class TestMomentumStrategy:
    def test_momentum_weights(self):
        strat = MomentumStrategy(lookback=20, long_only=True, name="mom")
        features = pd.DataFrame(
            {"momentum": [0.05, 0.02, -0.03]},
            index=["A", "B", "C"],
        )
        w = strat.generate_weights(datetime.now(), features)
        assert w.abs().sum() == pytest.approx(1.0, rel=1e-6)
        assert w["A"] > w["C"]  # higher momentum → higher weight


class TestEqualWeightStrategy:
    def test_equal_weight(self):
        strat = EqualWeightStrategy()
        features = pd.DataFrame(
            {"f": [1, 2, 3]},
            index=["A", "B", "C"],
        )
        w = strat.generate_weights(datetime.now(), features)
        assert len(w) == 3
        assert all(v == pytest.approx(1.0 / 3) for v in w)
