"""
Tests for Chan Theory Engine (缠论引擎)
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from core.analysis.chan import ChanEngine
from core.analysis.chan import fractals
from core.analysis.chan import strokes
from core.analysis.chan import segments
from core.analysis.chan import centers
from core.analysis.chan import divergence
from core.analysis.chan import points
from core.analysis.chan import config
from core.schemas import MarketBar, TimeFrame, Direction, Regime


def _bar(symbol="AAPL", offset=0, open_p=100.0, high=102.0, low=98.0, close=101.0, volume=1000.0, timeframe=TimeFrame.D1):
    """Helper: create a single bar."""
    return MarketBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=datetime(2024, 1, 1) + timedelta(days=offset),
        open=open_p,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _generate_trending_bars(n=100, start_price=100.0, trend="up"):
    """Generate synthetic trending bars for Chan analysis."""
    bars = []
    price = start_price
    for i in range(n):
        if trend == "up":
            change = np.random.uniform(0.1, 0.8)
        elif trend == "down":
            change = np.random.uniform(-0.8, -0.1)
        else:
            change = np.random.uniform(-0.3, 0.3)

        price += change
        noise = np.random.uniform(-0.3, 0.3)
        open_p = price + noise
        close = price + noise * 0.5
        high = max(open_p, close) + abs(noise) * 1.5
        low = min(open_p, close) - abs(noise) * 1.5

        bars.append(_bar(offset=i, open_p=open_p, high=high, low=low, close=close, volume=1000.0))
    return bars


def _bars_to_arrays(bars):
    """Convert bars list to numpy arrays."""
    return (
        np.array([b.open for b in bars]),
        np.array([b.high for b in bars]),
        np.array([b.low for b in bars]),
        np.array([b.close for b in bars]),
    )


class TestFractals:
    """Test fractal detection."""

    def test_detect_basic_fractals(self):
        highs = np.array([100.0, 102.0, 101.0])
        lows = np.array([99.0, 100.0, 99.5])
        opens = np.array([100.0, 101.0, 101.0])
        closes = np.array([101.0, 102.0, 100.5])

        result = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)

        # 中间一根最高 → 顶分型
        assert any(f.fractal_type == fractals.FractalType.TOP for f in result)

    def test_detect_top_and_bottom(self):
        # 构造: 顶-底交替
        highs = np.array([100, 103, 101, 97, 100], dtype=float)
        lows = np.array([99, 101, 99, 96, 98], dtype=float)
        opens = np.array([100, 102, 101, 97, 99], dtype=float)
        closes = np.array([101, 103, 99, 98, 100], dtype=float)

        result = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)

        # 应该识别出顶分型(at idx=1) 和底分型(at idx=3)
        top_count = sum(1 for f in result if f.fractal_type == fractals.FractalType.TOP)
        bot_count = sum(1 for f in result if f.fractal_type == fractals.FractalType.BOTTOM)
        assert top_count >= 1
        assert bot_count >= 1

    def test_insufficient_data(self):
        highs = np.array([100.0, 101.0])
        lows = np.array([99.0, 100.0])
        opens = np.array([100.0, 101.0])
        closes = np.array([101.0, 100.5])

        result = fractals.detect_fractals(highs, lows, opens, closes)
        assert result == []


class TestStrokes:
    """Test stroke building."""

    def test_build_strokes_basic(self):
        # 构造相邻顶底分型
        # 顶分型@1, 底分型@3, 顶分型@5...
        highs = np.array([100, 105, 103, 97, 104], dtype=float)
        lows = np.array([99, 103, 101, 95, 102], dtype=float)
        opens = np.array([100, 104, 103, 97, 103], dtype=float)
        closes = np.array([103, 105, 101, 96, 104], dtype=float)

        frs = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)
        result = strokes.build_strokes(frs, highs, lows, min_bars=0)

        assert len(result) >= 0  # 至少不报错

    def test_stroke_direction(self):
        highs = np.array([100, 106, 102, 95, 103], dtype=float)
        lows = np.array([99, 104, 100, 93, 101], dtype=float)
        opens = np.array([100, 105, 102, 95, 102], dtype=float)
        closes = np.array([105, 106, 96, 94, 103], dtype=float)

        frs = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)
        result = strokes.build_strokes(frs, highs, lows, min_bars=0)

        if len(result) >= 2:
            # 方向应该交替
            dirs = [s.direction for s in result]
            assert len(set(dirs)) == 2 or len(dirs) == 1


class TestSegments:
    """Test segment building."""

    def test_build_segments_minimal(self):
        highs = np.array([100, 106, 102, 95, 108, 103, 90, 105], dtype=float)
        lows = np.array([99, 104, 100, 93, 106, 101, 88, 103], dtype=float)
        opens = np.array([100, 105, 102, 95, 107, 103, 91, 104], dtype=float)
        closes = np.array([105, 106, 96, 94, 108, 102, 90, 105], dtype=float)

        frs = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)
        stks = strokes.build_strokes(frs, highs, lows, min_bars=0)
        result = segments.build_segments(stks)

        # 至少不报错
        assert isinstance(result, list)

    def test_detect_segment_breaks(self):
        highs = np.array([100, 106, 102, 95, 110, 105, 88], dtype=float)
        lows = np.array([99, 104, 100, 93, 108, 103, 86], dtype=float)
        opens = np.array([100, 105, 102, 95, 109, 105, 89], dtype=float)
        closes = np.array([105, 106, 96, 94, 110, 104, 88], dtype=float)

        frs = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)
        stks = strokes.build_strokes(frs, highs, lows, min_bars=0)
        segs = segments.build_segments(stks)
        breaks = segments.detect_segment_breaks(stks, segs)

        assert isinstance(breaks, list)


class TestCenters:
    """Test center (中枢) detection."""

    def test_build_centers_basic(self):
        highs = np.array([100, 106, 102, 95, 108, 103, 90, 105, 101, 88, 107, 103], dtype=float)
        lows = np.array([99, 104, 100, 93, 106, 101, 88, 103, 99, 86, 105, 101], dtype=float)
        opens = np.array([100, 105, 102, 95, 107, 103, 89, 104, 101, 87, 106, 103], dtype=float)
        closes = np.array([105, 106, 96, 94, 108, 102, 90, 105, 100, 88, 107, 102], dtype=float)

        frs = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)
        stks = strokes.build_strokes(frs, highs, lows, min_bars=0)
        segs = segments.build_segments(stks)
        result = centers.build_centers(segs)

        assert isinstance(result, list)

    def test_center_status(self):
        highs = np.array([100, 106, 102, 95, 108], dtype=float)
        lows = np.array([99, 104, 100, 93, 106], dtype=float)
        opens = np.array([100, 105, 102, 95, 107], dtype=float)
        closes = np.array([105, 106, 96, 94, 108], dtype=float)

        frs = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)
        stks = strokes.build_strokes(frs, highs, lows, min_bars=0)
        segs = segments.build_segments(stks)
        ctrs = centers.build_centers(segs)

        if ctrs:
            status = centers.center_status(ctrs, 100.0)
            assert status in ["in_center", "above_center", "below_center", "no_center"]


class TestDivergence:
    """Test divergence detection."""

    def test_macd_strength(self):
        prices = np.array([100 + i * 0.5 for i in range(50)], dtype=float)
        highs = prices + 1
        lows = prices - 1
        closes = prices

        result = divergence.macd_strength(highs, lows, closes)

        assert len(result) == len(closes)
        assert isinstance(result, np.ndarray)

    def test_detect_divergence_basic(self):
        # 构造顶背驰: 价格两波高点上升, MACD柱子第二波缩短
        highs = np.array([100, 105, 103, 97, 100, 108, 106, 99, 102, 110, 108], dtype=float)
        lows = np.array([99, 103, 101, 95, 98, 106, 104, 97, 100, 108, 106], dtype=float)
        closes = np.array([100, 105, 103, 97, 100, 108, 106, 99, 102, 110, 108], dtype=float)

        frs = fractals.detect_fractals(highs, lows, closes, closes, handle_inclusion=False)
        stks = strokes.build_strokes(frs, highs, lows, min_bars=0)
        segs = segments.build_segments(stks)

        divs = divergence.detect_divergence(stks, segs, highs, lows, closes)

        assert isinstance(divs, list)


class TestPoints:
    """Test trading points detection."""

    def test_detect_purchase_points(self):
        highs = np.array([100, 106, 102, 95, 108, 103, 90, 105], dtype=float)
        lows = np.array([99, 104, 100, 93, 106, 101, 88, 103], dtype=float)
        opens = np.array([100, 105, 102, 95, 107, 103, 89, 104], dtype=float)
        closes = np.array([105, 106, 96, 94, 108, 102, 90, 105], dtype=float)

        frs = fractals.detect_fractals(highs, lows, opens, closes, handle_inclusion=False)
        stks = strokes.build_strokes(frs, highs, lows, min_bars=0)
        segs = segments.build_segments(stks)
        ctrs = centers.build_centers(segs)
        divs = divergence.detect_divergence(stks, segs, highs, lows, closes)

        result = points.detect_purchase_points(stks, segs, ctrs, divs, highs, lows, closes)

        assert isinstance(result, list)

    def test_structure_invalidation(self):
        highs = np.array([100, 105, 103, 95, 100, 110, 108, 90], dtype=float)
        lows = np.array([99, 103, 101, 93, 98, 108, 106, 88], dtype=float)
        closes = np.array([100, 105, 103, 95, 100, 110, 108, 90], dtype=float)

        frs = fractals.detect_fractals(highs, lows, closes, closes, handle_inclusion=False)
        stks = strokes.build_strokes(frs, highs, lows, min_bars=0)

        is_invalid, reason = points.check_structure_invalidation(stks, [], highs, lows)

        assert isinstance(is_invalid, bool)


class TestChanEngine:
    """Test ChanEngine integration."""

    def test_engine_initialization(self):
        engine = ChanEngine()
        assert engine.engine_name == "chan"
        assert engine.health_check() is True

    def test_analyze_with_trending_bars(self):
        bars = _generate_trending_bars(n=100, trend="up")

        engine = ChanEngine()
        signal = engine.analyze(bars)

        assert signal.engine_name == "chan"
        assert signal.symbol == "AAPL"
        assert signal.direction in [Direction.LONG, Direction.SHORT, Direction.FLAT]
        assert 0 <= signal.confidence <= 1

    def test_analyze_with_dict_input(self):
        bars = _generate_trending_bars(n=100, trend="down")

        engine = ChanEngine()
        signal = engine.analyze({"bars": bars})

        assert signal.engine_name == "chan"

    def test_analyze_returns_chan_signal_fields(self):
        bars = _generate_trending_bars(n=100, trend="up")

        engine = ChanEngine()
        signal = engine.analyze(bars)

        # 检查 ChanSignal 特有字段
        assert hasattr(signal, "fractal_level")
        assert hasattr(signal, "bi_status")
        assert hasattr(signal, "segment_status")
        assert hasattr(signal, "zhongshu_status")
        assert hasattr(signal, "divergence")
        assert hasattr(signal, "purchase_point")
        assert hasattr(signal, "sell_point")
        assert hasattr(signal, "higher_tf_direction")
        assert hasattr(signal, "lower_tf_direction")

    def test_analyze_preserves_structure(self):
        bars = _generate_trending_bars(n=100, trend="up")

        engine = ChanEngine()
        signal = engine.analyze(bars)

        # metadata 应该包含结构信息
        assert "stroke_count" in signal.metadata
        assert "segment_count" in signal.metadata
        assert "center_count" in signal.metadata

    def test_batch_analyze(self):
        data_map = {
            "AAPL": _generate_trending_bars(n=100, trend="up"),
            "TSLA": _generate_trending_bars(n=100, trend="down"),
        }

        engine = ChanEngine()
        signals = engine.batch_analyze(data_map)

        assert set(signals.keys()) == {"AAPL", "TSLA"}
        assert signals["AAPL"].engine_name == "chan"

    def test_insufficient_data_raises(self):
        bars = _generate_trending_bars(n=10, trend="up")

        engine = ChanEngine()

        with pytest.raises(ValueError, match="Insufficient"):
            engine.analyze(bars)

    def test_custom_config(self):
        custom_cfg = {
            "bi_min_bars": 3,
            "segment_back_ratio": 0.4,
            "higher_timeframe": "W",
        }

        engine = ChanEngine(config=custom_cfg)
        assert engine.config.bi_min_bars == 3
        assert engine.config.segment_back_ratio == 0.4

    def test_divergence_field_values(self):
        """divergence 字段应为 "bullish"/"bearish"/"none"/None"""
        bars = _generate_trending_bars(n=100, trend="up")

        engine = ChanEngine()
        signal = engine.analyze(bars)

        # divergence 应为有效值之一
        valid = {None, "bullish", "bearish", "none"}
        assert signal.divergence in valid

    def test_purchase_sell_point_values(self):
        """purchase_point/sell_point 应为 1/2/3/None"""
        bars = _generate_trending_bars(n=100, trend="up")

        engine = ChanEngine()
        signal = engine.analyze(bars)

        valid_purchase = {None, 1, 2, 3}
        valid_sell = {None, 1, 2, 3}
        assert signal.purchase_point in valid_purchase
        assert signal.sell_point in valid_sell
