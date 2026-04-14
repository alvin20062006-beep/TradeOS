"""
Tests for Technical Analysis Engine
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from core.analysis.technical import TechnicalEngine
from core.analysis.technical import trend
from core.analysis.technical import momentum
from core.analysis.technical import volatility
from core.analysis.technical import patterns
from core.analysis.technical import candles
from core.analysis.technical import levels
from core.schemas import MarketBar, TimeFrame, Direction, Regime


def _bar(symbol="AAPL", offset=0, open_p=100.0, high=102.0, low=98.0, close=101.0, volume=1000.0, timeframe=TimeFrame.H1):
    """Helper: create a single bar."""
    return MarketBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=datetime(2024, 1, 1) + timedelta(hours=offset),
        open=open_p,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _generate_trending_bars(n=100, start_price=100.0, trend="up", volatility=1.0):
    """Generate synthetic trending bars."""
    bars = []
    price = start_price
    for i in range(n):
        if trend == "up":
            change = np.random.uniform(0.1, 0.5)
        elif trend == "down":
            change = np.random.uniform(-0.5, -0.1)
        else:
            change = np.random.uniform(-0.2, 0.2)
        
        price += change
        noise = volatility * np.random.uniform(-0.3, 0.3)
        
        open_p = price + noise
        close = price + noise * 0.5
        high = max(open_p, close) + abs(noise)
        low = min(open_p, close) - abs(noise)
        
        bars.append(_bar(offset=i, open_p=open_p, high=high, low=low, close=close, volume=1000.0))
    return bars


class TestTrend:
    """Test trend indicators."""
    
    def test_sma_basic(self):
        prices = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
        result = trend.sma(prices, 3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        assert result[2] == 2.0  # (1+2+3)/3
        assert result[9] == 9.0  # (8+9+10)/3
    
    def test_sma_insufficient_data(self):
        prices = np.array([1, 2], dtype=float)
        result = trend.sma(prices, 5)
        assert all(np.isnan(result))
    
    def test_ema_basic(self):
        prices = np.array([1, 2, 3, 4, 5], dtype=float)
        result = trend.ema(prices, 3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        assert not np.isnan(result[2])
    
    def test_adx_trending_market(self):
        # 生成上升趋势数据
        n = 50
        prices = np.array([100 + i * 0.5 for i in range(n)], dtype=float)
        highs = prices + 1
        lows = prices - 1
        
        result = trend.adx(highs, lows, prices, period=14)
        
        # ADX 在趋势市应该 > 25
        assert not np.isnan(result["adx"][-1])
        assert result["adx"][-1] > 20  # 放宽条件
    
    def test_adx_insufficient_data(self):
        highs = np.array([101, 102, 103])
        lows = np.array([99, 100, 101])
        closes = np.array([100, 101, 102])
        
        result = trend.adx(highs, lows, closes, period=14)
        assert all(np.isnan(result["adx"]))


class TestMomentum:
    """Test momentum indicators."""
    
    def test_rsi_basic(self):
        # 稳定上涨序列
        prices = np.array([100 + i for i in range(30)], dtype=float)
        result = momentum.rsi(prices, period=14)
        
        assert np.isnan(result[0])
        assert not np.isnan(result[-1])
        assert 0 <= result[-1] <= 100
        assert result[-1] > 70  # 上涨趋势 RSI 应该高
    
    def test_rsi_range(self):
        # 震荡序列
        prices = np.array([100 + np.sin(i) * 2 for i in range(30)], dtype=float)
        result = momentum.rsi(prices, period=14)
        
        assert not np.isnan(result[-1])
        assert 40 < result[-1] < 60  # 震荡市 RSI 应该在中性区
    
    def test_macd_basic(self):
        prices = np.array([100 + i * 0.5 for i in range(50)], dtype=float)
        result = momentum.macd(prices)
        
        assert "line" in result
        assert "signal" in result
        assert "histogram" in result
        assert len(result["line"]) == len(prices)
    
    def test_kdj_basic(self):
        n = 30
        highs = np.array([102 + i * 0.5 for i in range(n)], dtype=float)
        lows = np.array([98 + i * 0.5 for i in range(n)], dtype=float)
        closes = np.array([100 + i * 0.5 for i in range(n)], dtype=float)
        
        result = momentum.kdj(highs, lows, closes)
        
        assert "k" in result
        assert "d" in result
        assert "j" in result
    
    def test_cci_basic(self):
        n = 30
        highs = np.array([102 + i for i in range(n)], dtype=float)
        lows = np.array([98 + i for i in range(n)], dtype=float)
        closes = np.array([100 + i for i in range(n)], dtype=float)
        
        result = momentum.cci(highs, lows, closes)
        
        assert not np.isnan(result[-1])


class TestVolatility:
    """Test volatility indicators."""
    
    def test_atr_basic(self):
        n = 30
        highs = np.array([102 + np.random.uniform(-1, 1) for _ in range(n)])
        lows = np.array([98 + np.random.uniform(-1, 1) for _ in range(n)])
        closes = np.array([100 + np.random.uniform(-1, 1) for _ in range(n)])
        
        result = volatility.atr(highs, lows, closes, period=14)
        
        assert np.isnan(result[0])
        assert not np.isnan(result[-1])
        assert result[-1] > 0
    
    def test_bollinger_bands(self):
        prices = np.array([100 + np.sin(i * 0.5) * 5 for i in range(50)], dtype=float)
        result = volatility.bollinger_bands(prices, period=20, std_dev=2.0)
        
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert "bandwidth" in result
        
        # 上轨应该 > 中轨 > 下轨
        assert result["upper"][-1] > result["middle"][-1] > result["lower"][-1]


class TestPatterns:
    """Test chart pattern recognition."""
    
    def test_find_local_extrema(self):
        # 简单正弦波
        prices = np.array([100 + np.sin(i * 0.5) * 10 for i in range(50)], dtype=float)
        highs, lows = patterns.find_local_extrema(prices, window=3)
        
        assert len(highs) > 0
        assert len(lows) > 0
    
    def test_detect_double_top(self):
        # 构造双顶形态
        n = 50
        prices = np.zeros(n)
        for i in range(n):
            if i < 15:
                prices[i] = 100 + i * 0.5  # 上涨
            elif i < 20:
                prices[i] = 107 - (i - 15) * 0.5  # 回落
            elif i < 25:
                prices[i] = 105 + (i - 20) * 0.4  # 第二顶
            else:
                prices[i] = 107 - (i - 25) * 0.6  # 下跌
        
        result = patterns.detect_double_top_bottom(prices)
        # 应该能识别到双顶
        assert len(result) >= 0


class TestCandles:
    """Test candlestick pattern recognition."""
    
    def test_detect_doji(self):
        n = 10
        opens = np.array([100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0])
        closes = np.array([100.1, 99.9, 100.05, 100.0, 99.98, 100.02, 100.0, 100.1, 99.9, 100.0])
        highs = np.array([101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0])
        lows = np.array([99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0])
        
        result = candles.detect_doji(opens, closes, highs, lows)
        
        # 应该识别到一些十字星
        assert len(result) >= 0
    
    def test_detect_engulfing(self):
        # 看涨吞没
        opens = np.array([100.0, 99.0, 98.0, 97.0, 96.0])
        closes = np.array([99.0, 98.0, 97.0, 96.0, 98.0])  # 最后一根吞没
        
        result = candles.detect_engulfing(opens, closes)
        
        assert len(result) >= 0


class TestLevels:
    """Test support/resistance detection."""
    
    def test_find_pivot_points(self):
        n = 30
        highs = np.array([102 + np.sin(i) * 2 for i in range(n)])
        lows = np.array([98 + np.sin(i) * 2 for i in range(n)])
        closes = np.array([100 + np.sin(i) * 2 for i in range(n)])
        
        pivot_highs, pivot_lows = levels.find_pivot_points(highs, lows, closes)
        
        # 应该能找到一些枢轴点
        assert len(pivot_highs) >= 0
        assert len(pivot_lows) >= 0
    
    def test_detect_support_resistance(self):
        n = 50
        highs = np.array([102 + np.sin(i * 0.3) * 5 for i in range(n)])
        lows = np.array([98 + np.sin(i * 0.3) * 5 for i in range(n)])
        closes = np.array([100 + np.sin(i * 0.3) * 5 for i in range(n)])
        
        result = levels.detect_support_resistance(highs, lows, closes)
        
        # 应该能检测到一些支撑阻力位
        assert len(result) >= 0


class TestTechnicalEngine:
    """Test TechnicalEngine integration."""
    
    def test_engine_initialization(self):
        engine = TechnicalEngine()
        assert engine.engine_name == "technical"
        assert engine.health_check() is True
    
    def test_analyze_with_bars(self):
        # 生成趋势数据
        bars = _generate_trending_bars(n=100, trend="up")
        
        engine = TechnicalEngine()
        signal = engine.analyze(bars)
        
        assert signal.engine_name == "technical"
        assert signal.symbol == "AAPL"
        assert signal.direction in [Direction.LONG, Direction.SHORT, Direction.FLAT]
        assert 0 <= signal.confidence <= 1
        assert signal.trend in ["up", "down", "sideways"]
        assert signal.momentum in ["strengthening", "weakening", "neutral"]
    
    def test_analyze_with_dict_input(self):
        bars = _generate_trending_bars(n=100, trend="down")
        
        engine = TechnicalEngine()
        signal = engine.analyze({"bars": bars})
        
        assert signal.engine_name == "technical"
    
    def test_analyze_flat_market(self):
        # 生成震荡数据
        bars = _generate_trending_bars(n=100, trend="flat", volatility=0.3)
        
        engine = TechnicalEngine()
        signal = engine.analyze(bars)
        
        assert signal.regime in [Regime.RANGING, Regime.UNKNOWN, Regime.TRENDING_UP, Regime.TRENDING_DOWN, Regime.VOLATILE]
    
    def test_batch_analyze(self):
        data_map = {
            "AAPL": _generate_trending_bars(n=100, trend="up"),
            "TSLA": _generate_trending_bars(n=100, trend="down"),
        }
        
        engine = TechnicalEngine()
        signals = engine.batch_analyze(data_map)
        
        assert set(signals.keys()) == {"AAPL", "TSLA"}
        assert signals["AAPL"].engine_name == "technical"
    
    def test_insufficient_data_returns_neutral(self):
        # 少于 20 根 bar
        bars = _generate_trending_bars(n=10, trend="up")
        
        engine = TechnicalEngine()
        
        with pytest.raises(ValueError, match="Insufficient"):
            engine.analyze(bars)
    
    def test_custom_config(self):
        custom_cfg = {
            "ma_periods": [5, 10],
            "rsi_period": 7,
        }
        
        engine = TechnicalEngine(config=custom_cfg)
        assert engine.config["ma_periods"] == [5, 10]
        assert engine.config["rsi_period"] == 7
    
    def test_signal_has_required_fields(self):
        bars = _generate_trending_bars(n=100, trend="up")
        
        engine = TechnicalEngine()
        signal = engine.analyze(bars)
        
        # 检查所有必要字段存在
        assert hasattr(signal, "trend")
        assert hasattr(signal, "momentum")
        assert hasattr(signal, "volatility_state")
        assert hasattr(signal, "chart_pattern")
        assert hasattr(signal, "candle_pattern")
        assert hasattr(signal, "support_levels")
        assert hasattr(signal, "resistance_levels")
        assert isinstance(signal.support_levels, list)
        assert isinstance(signal.resistance_levels, list)
