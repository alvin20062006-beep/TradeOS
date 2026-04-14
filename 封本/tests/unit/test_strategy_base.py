"""
tests/unit/test_strategy_base.py
============================
Unit tests for StrategyBase.
"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock

from core.research.strategy.base import StrategyBase
from core.research.strategy.signal import SignalDirection


class DummyStrategy(StrategyBase):
    """Concrete implementation for testing."""

    def __init__(self, name="test", long_only=True):
        super().__init__(name=name, description="Test strategy")
        self.long_only = long_only

    def generate_weights(self, timestamp, features):
        n = len(features)
        w = pd.Series(1.0 / n, index=features.index)
        if not self.long_only:
            # flip sign of first half
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
        assert list(w.index) == ["AAPL", "GOOG", "MSFT"]

    def test_generate_weights_with_shorts(self):
        s = DummyStrategy(long_only=False)
        features = pd.DataFrame(
            {"feat1": [1, 2, 3, 4]},
            index=["A", "B", "C", "D"],
        )
        w = s.generate_weights(datetime.now(), features)
        assert w.sum() == pytest.approx(0.0)  # long-short, net zero
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
        assert intent.metadata["strategy_name"] == "test"

    def test_generate_weights_series(self):
        s = DummyStrategy()
        dates = pd.date_range("2024-01-01", periods=3, freq="D")
        features_by_date = {
            d: pd.DataFrame(
                {"f": [1.0, 2.0]},
                index=["AAPL", "GOOG"],
            )
            for d in dates
        }
        df = s.generate_weights_series(dates, features_by_date)
        assert df.shape == (3, 2)
        assert df.index.equals(dates)
        assert all(df.sum(axis=1).round(6) == 1.0)

    def test_abstract_method_required(self):
        class BadStrategy(StrategyBase):
            """Missing generate_weights implementation."""

            pass

        with pytest.raises(TypeError, match="abstract"):
            BadStrategy()
