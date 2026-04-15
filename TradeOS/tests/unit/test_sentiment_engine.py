"""
Tests for Sentiment Engine
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from core.analysis.sentiment import SentimentEngine
from core.analysis.sentiment import news_sentiment
from core.analysis.sentiment import volume_metrics
from core.analysis.sentiment import oi_proxy
from core.analysis.sentiment import money_flow
from core.analysis.sentiment import regime
from core.analysis.sentiment import crowding
from core.schemas import NewsEvent, MarketBar, TimeFrame


def _bar(symbol="AAPL", offset=0, open_p=100.0, high=102.0, low=98.0, close=101.0, volume=1000.0):
    return MarketBar(
        symbol=symbol,
        timeframe=TimeFrame.D1,
        timestamp=datetime(2024, 1, 1) + timedelta(days=offset),
        open=open_p,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _generate_bars(n=100, start_price=100.0, trend="up"):
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
        noise = np.random.uniform(-0.2, 0.2)
        open_p = price + noise
        close = price + noise * 0.5
        high = max(open_p, close) + abs(noise)
        low = min(open_p, close) - abs(noise)
        volume = np.random.uniform(800, 1200)
        bars.append(_bar(offset=i, open_p=open_p, high=high, low=low, close=close, volume=volume))
    return bars


def _news_event(title="Test news", sentiment_score=0.5, offset=0):
    return NewsEvent(
        timestamp=datetime(2024, 1, 1) + timedelta(days=offset),
        title=title,
        source="test",
        sentiment_score=sentiment_score,
    )


class TestNewsSentiment:
    """Test news sentiment analysis."""

    def test_analyze_news_sentiment_bullish(self):
        events = [
            _news_event(title="Stock rallies on earnings beat", sentiment_score=0.8),
            _news_event(title="Strong guidance issued", sentiment_score=0.7),
        ]
        result = news_sentiment.analyze_news_sentiment(events)

        assert result.news_sentiment > 0.5
        assert result.sentiment_label == "bullish"

    def test_analyze_news_sentiment_bearish(self):
        events = [
            _news_event(title="Stock drops on guidance cut", sentiment_score=-0.6),
            _news_event(title="Analyst downgrades", sentiment_score=-0.7),
        ]
        result = news_sentiment.analyze_news_sentiment(events)

        assert result.news_sentiment < -0.2
        assert result.sentiment_label == "bearish"

    def test_proxy_news_sentiment(self):
        closes = np.array([100 + i * 0.5 for i in range(30)], dtype=float)
        volumes = np.ones(30) * 1000
        volumes[-5:] = 1500  # 放量

        result = news_sentiment.proxy_news_sentiment_from_returns(closes, volumes)

        # 价格上涨 → bullish
        assert result.news_sentiment > 0
        assert result.sentiment_label in ["bullish", "neutral"]

    def test_empty_news(self):
        result = news_sentiment.analyze_news_sentiment([])

        assert result.news_sentiment == 0.0
        assert result.sources_count == 0


class TestVolumeMetrics:
    """Test volume surprise and crowding."""

    def test_volume_surprise_spike(self):
        volumes = np.ones(30) * 1000
        volumes[-5:] = 3000  # 3x 放量

        result = volume_metrics.calc_volume_surprise(volumes)

        assert result.volume_surprise > 2.0
        assert result.volume_trend == "increasing"

    def test_volume_surprise_normal(self):
        volumes = np.ones(30) * 1000

        result = volume_metrics.calc_volume_surprise(volumes)

        assert 0.8 < result.volume_surprise < 1.2

    def test_extreme_crowding(self):
        volumes = np.ones(30) * 1000
        volumes[-1] = 5000  # 5x 放量

        is_extreme, desc = volume_metrics.detect_extreme_crowding(volumes)

        assert is_extreme is True


class TestOIProxy:
    """Test OI/Funding proxy."""

    def test_proxy_oi_from_volume(self):
        result = oi_proxy.proxy_oi_from_volume(
            recent_volume=3000,
            avg_volume=1000,
            price_change_pct=0.05,
        )

        assert result.is_proxy is True
        assert result.oi_change_pct > 0

    def test_liquidation_zones(self):
        zones = oi_proxy.get_liquidation_zones_proxy(current_price=100.0)

        assert len(zones) == 2
        assert zones[0][2] == "long_liquidation"
        assert zones[1][2] == "short_liquidation"


class TestMoneyFlow:
    """Test money flow analysis."""

    def test_money_flow_accumulation(self):
        # 构造上涨 + 放量
        n = 20
        closes = np.array([100 + i for i in range(n)], dtype=float)
        highs = closes + 1
        lows = closes - 1
        volumes = np.ones(n) * 1000

        result = money_flow.calc_money_flow(highs, lows, closes, volumes)

        assert result.money_flow_index > 50
        assert result.accumulation in ["accumulation", "neutral"]

    def test_money_flow_distribution(self):
        # 构造下跌 + 放量
        n = 20
        closes = np.array([100 - i for i in range(n)], dtype=float)
        highs = closes + 1
        lows = closes - 1
        volumes = np.ones(n) * 1000

        result = money_flow.calc_money_flow(highs, lows, closes, volumes)

        assert result.money_flow_index < 50
        assert result.accumulation in ["distribution", "neutral"]


class TestRegime:
    """Test sentiment regime detection."""

    def test_risk_on_regime(self):
        # 构造上涨 + 低波动 + 放量
        n = 30
        closes = np.array([100 + i * 0.3 for i in range(n)], dtype=float)
        highs = closes + 0.5
        lows = closes - 0.5
        volumes = np.ones(n) * 1000
        volumes[-5:] = 1200

        result = regime.detect_sentiment_regime(closes, highs, lows, volumes)

        # 可能检测到 risk_on 或 neutral
        assert result.regime in [regime.SentimentRegime.RISK_ON, regime.SentimentRegime.NEUTRAL]

    def test_risk_off_regime(self):
        # 构造下跌 + 高波动 + 放量
        n = 30
        closes = np.array([100 - i * 0.5 for i in range(n)], dtype=float)
        highs = closes + 2.0  # 高波动
        lows = closes - 2.0
        volumes = np.ones(n) * 1000
        volumes[-5:] = 2000

        result = regime.detect_sentiment_regime(closes, highs, lows, volumes)

        assert result.regime in [regime.SentimentRegime.RISK_OFF, regime.SentimentRegime.NEUTRAL]

    def test_fear_greed_index(self):
        closes = np.array([100 + i for i in range(50)], dtype=float)
        result = regime.simple_fear_greed_index(closes)

        # 价格在上半区间 → 贪婪
        assert result > 50


class TestCrowding:
    """Test crowding and squeeze detection."""

    def test_long_crowding(self):
        # 价格持续上涨
        n = 30
        closes = np.array([100 + i * 0.5 for i in range(n)], dtype=float)
        volumes = np.ones(n) * 1000

        result = crowding.detect_crowding(closes, volumes)

        assert result.long_crowding > result.short_crowding
        assert result.crowding_direction in ["long", "neutral"]

    def test_short_crowding(self):
        # 价格持续下跌
        n = 30
        closes = np.array([100 - i * 0.5 for i in range(n)], dtype=float)
        volumes = np.ones(n) * 1000

        result = crowding.detect_crowding(closes, volumes)

        assert result.short_crowding > result.long_crowding
        assert result.crowding_direction in ["short", "neutral"]

    def test_squeeze_risk(self):
        # 空头拥挤 + 反弹
        n = 30
        closes = np.array([100 - i * 0.3 for i in range(n)], dtype=float)
        closes[-2:] = closes[-3] + np.array([0.5, 1.0])  # 反弹
        volumes = np.ones(n) * 1000
        volumes[-5:] = 2000

        result = crowding.detect_crowding(closes, volumes)

        # 可能检测到 short squeeze 风险
        assert result.squeeze_risk in ["none", "short_squeeze"]


class TestSentimentEngine:
    """Test SentimentEngine integration."""

    def test_engine_initialization(self):
        engine = SentimentEngine()
        assert engine.engine_name == "sentiment"
        assert engine.health_check() is True

    def test_analyze_with_bars_proxy(self):
        bars = _generate_bars(n=50, trend="up")
        engine = SentimentEngine()
        signal = engine.analyze(bars)

        assert signal.symbol == "AAPL"
        assert signal.metadata.get("proxy") is True
        assert 0 <= signal.composite_sentiment <= 1

    def test_analyze_with_news(self):
        bars = _generate_bars(n=50)
        news = [
            _news_event(title="Strong earnings", sentiment_score=0.8),
            _news_event(title="Upgraded", sentiment_score=0.7),
        ]
        engine = SentimentEngine()
        signal = engine.analyze(bars, news_events=news)

        assert signal.metadata.get("proxy") is False
        assert signal.news_sentiment > 0.5

    def test_analyze_with_dict_input(self):
        data = {
            "bars": _generate_bars(n=50, trend="down"),
            "news": [{"timestamp": datetime.utcnow(), "title": "Bad news", "source": "test", "sentiment_score": -0.5}],
        }
        engine = SentimentEngine()
        signal = engine.analyze(data)

        # composite 由新闻情绪主导（-0.5 → 0.25），应该低于 0.5
        assert signal.news_sentiment == 0.25  # -0.5 → (0.5)/2 = 0.25

    def test_signal_fields(self):
        bars = _generate_bars(n=50)
        engine = SentimentEngine()
        signal = engine.analyze(bars)

        # 检查所有字段
        assert hasattr(signal, "news_sentiment")
        assert hasattr(signal, "social_sentiment")
        assert hasattr(signal, "composite_sentiment")
        assert hasattr(signal, "bullish_ratio")
        assert hasattr(signal, "bearish_ratio")

    def test_metadata_detail(self):
        bars = _generate_bars(n=50, trend="up")
        engine = SentimentEngine()
        signal = engine.analyze(bars)

        # 检查 metadata 详情
        assert "news_detail" in signal.metadata
        assert "volume_detail" in signal.metadata
        assert "oi_detail" in signal.metadata
        assert "money_flow_detail" in signal.metadata
        assert "regime_detail" in signal.metadata
        assert "crowding_detail" in signal.metadata

    def test_batch_analyze(self):
        data_map = {
            "AAPL": _generate_bars(n=50, trend="up"),
            "TSLA": _generate_bars(n=50, trend="down"),
        }
        engine = SentimentEngine()
        signals = engine.batch_analyze(data_map)

        assert set(signals.keys()) == {"AAPL", "TSLA"}

    def test_custom_config(self):
        engine = SentimentEngine(config={"lookback": 30, "crowding_threshold": 0.9})
        assert engine.config["lookback"] == 30

    def test_regime_field_values(self):
        bars = _generate_bars(n=50, trend="up")
        engine = SentimentEngine()
        signal = engine.analyze(bars)

        regime_val = signal.metadata["regime_detail"]["regime"]
        assert regime_val in ["risk_on", "risk_off", "neutral"]

    def test_crowding_squeeze_field(self):
        bars = _generate_bars(n=50, trend="up")
        engine = SentimentEngine()
        signal = engine.analyze(bars)

        squeeze = signal.metadata["crowding_detail"]["squeeze_risk"]
        assert squeeze in ["none", "short_squeeze", "long_squeeze"]
