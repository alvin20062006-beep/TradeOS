"""
Tests for core/analysis/base.py
"""

import pytest
from datetime import datetime
from core.analysis.base import AnalysisEngine
from core.schemas import MarketBar, Direction, Regime, TimeFrame


class DummyEngine(AnalysisEngine):
    """Minimal concrete implementation for testing."""

    engine_name = "dummy"

    def analyze(self, data, **kwargs):
        from core.schemas import EngineSignal
        bars = self._check_bars(data, min_length=2)
        return EngineSignal(
            engine_name=self.engine_name,
            symbol=bars[0].symbol,
            timestamp=bars[0].timestamp,
            direction=Direction.FLAT,
            confidence=0.5,
            regime=Regime.UNKNOWN,
            reasoning="dummy",
        )


def _bar(symbol="AAPL", offset=0, close=100.0, **kwargs):
    defaults = dict(symbol=symbol, timeframe=TimeFrame.H1, timestamp=datetime(2024, 1, 1) + __import__("datetime").timedelta(hours=offset), open=close - 0.5, high=close + 1.0, low=close - 1.0, close=close, volume=1000.0)
    defaults.update(kwargs)
    return MarketBar(**defaults)


class TestCheckBars:
    def test_list_of_dicts(self):
        bars = [_bar(offset=0), _bar(offset=1)]
        result = DummyEngine()._check_bars(bars)
        assert len(result) == 2
        assert all(isinstance(b, MarketBar) for b in result)

    def test_list_of_market_bar_objects(self):
        bars = [_bar(offset=0), _bar(offset=1)]
        result = DummyEngine()._check_bars(bars)
        assert len(result) == 2

    def test_dict_unwrap(self):
        result = DummyEngine()._check_bars({"bars": [_bar(offset=0), _bar(offset=1)]})
        assert len(result) == 2

    def test_single_bar_unwrap(self):
        result = DummyEngine()._check_bars(_bar(offset=0), min_length=1)
        assert len(result) == 1

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            DummyEngine()._check_bars([])

    def test_too_few_raises(self):
        with pytest.raises(ValueError, match="Insufficient"):
            DummyEngine()._check_bars([_bar()], min_length=3)

    def test_none_raises(self):
        with pytest.raises(ValueError, match="None"):
            DummyEngine()._check_bars(None)


class TestHealthCheck:
    def test_default_health_true(self):
        assert DummyEngine().health_check() is True


class TestBatchAnalyze:
    def test_batch_returns_dict(self):
        data_map = {
            "AAPL": [_bar(symbol="AAPL"), _bar(symbol="AAPL", offset=1)],
            "TSLA": [_bar(symbol="TSLA"), _bar(symbol="TSLA", offset=1)],
        }
        signals = DummyEngine().batch_analyze(data_map)
        assert set(signals.keys()) == {"AAPL", "TSLA"}

    def test_batch_error_wrapped_neutral(self):
        """Errors in a single symbol should not crash batch."""
        data_map = {
            "AAPL": [_bar(symbol="AAPL"), _bar(symbol="AAPL", offset=1)],
            "BAD": None,  # will cause error
        }
        signals = DummyEngine().batch_analyze(data_map)
        assert "BAD" in signals
        assert signals["BAD"].confidence == 0.0
        assert "error" in signals["BAD"].metadata


class TestRequireTimeframe:
    def test_from_bar(self):
        bars = [_bar(timeframe=TimeFrame.D1)]
        tf = DummyEngine()._require_timeframe(bars)
        assert "1d" in tf

    def test_default(self):
        bars = [_bar(timeframe=TimeFrame.H1)]
        tf = DummyEngine()._require_timeframe(bars)
        assert "1h" in tf
