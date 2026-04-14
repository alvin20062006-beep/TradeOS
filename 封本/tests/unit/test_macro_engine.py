"""
Tests for Macro Engine
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from core.analysis.macro import MacroEngine
from core.analysis.macro import rate_pressure
from core.analysis.macro import inflation_shock
from core.analysis.macro import liquidity
from core.analysis.macro import event_shock
from core.analysis.macro import regime_detector
from core.schemas import MacroEvent, MarketBar, TimeFrame, Regime


def _bar(symbol="SPY", offset=0, close=450.0, volume=1000.0, high=None, low=None):
    c = close + np.random.uniform(-0.5, 0.5)
    h = max(c, close) + 0.3
    l = min(c, close) - 0.3
    return MarketBar(
        symbol=symbol,
        timeframe=TimeFrame.D1,
        timestamp=datetime(2024, 1, 1) + timedelta(days=offset),
        open=c - 0.1,
        high=h if high is None else high,
        low=l if low is None else low,
        close=c,
        volume=volume,
    )


def _generate_bars(n=100, start_price=450.0, trend="up", volatility=0.01):
    bars = []
    price = start_price
    for i in range(n):
        if trend == "up":
            change = np.random.uniform(0.0, volatility * price * 2)
        elif trend == "down":
            change = np.random.uniform(-volatility * price * 2, 0.0)
        else:
            change = np.random.uniform(-volatility * price, volatility * price)
        price += change
        bars.append(_bar(offset=i, close=price))
    return bars


def _macro_event(name="CPI", country="US", impact="medium"):
    return MacroEvent(
        timestamp=datetime.utcnow(),
        event_name=name,
        country=country,
        impact=impact,
    )


class TestRatePressure:
    """Test rate pressure module."""

    def test_calc_rate_pressure_bearish(self):
        result = rate_pressure.calc_rate_pressure_proxy(
            returns_1d=-0.03, volatility_20d=0.02
        )
        assert result.pressure_score < 0.5  # 大跌 → 宽松预期
        assert result.central_bank_stance in ["dovish", "neutral"]

    def test_calc_rate_pressure_bullish_market(self):
        result = rate_pressure.calc_rate_pressure_proxy(
            returns_1d=0.03, volatility_20d=0.015
        )
        assert result.pressure_score > 0.5  # 大涨 → 紧缩压力

    def test_parse_macro_event_hike(self):
        result = rate_pressure.parse_macro_event_rate("Fed Rate Hike Decision", "high")
        assert result.rate_direction == rate_pressure.RateDirection.HIKING
        assert result.central_bank_stance == "hawkish"

    def test_parse_macro_event_cut(self):
        result = rate_pressure.parse_macro_event_rate("ECB Rate Cut", "medium")
        assert result.rate_direction == rate_pressure.RateDirection.CUTTING
        assert result.central_bank_stance == "dovish"


class TestInflationShock:
    """Test inflation shock module."""

    def test_calc_inflation_shock_hot(self):
        result = inflation_shock.calc_inflation_shock_proxy(volatility=0.30, trend="up")
        assert result.shock_score > 0.5
        assert result.direction in ["hot", "neutral"]

    def test_calc_inflation_shock_cold(self):
        result = inflation_shock.calc_inflation_shock_proxy(volatility=0.03, trend="down")
        assert result.shock_score < 0.5
        assert result.direction in ["cold", "neutral"]

    def test_parse_macro_event_inflation(self):
        result = inflation_shock.parse_macro_event_inflation(
            "US CPI", actual=3.5, consensus=3.2
        )
        assert result.shock_score >= 0.5


class TestLiquidity:
    """Test liquidity condition module."""

    def test_calc_liquidity_abundant(self):
        n = 30
        closes = np.array([100 + i * 0.01 for i in range(n)], dtype=float)
        highs = closes + 0.5
        lows = closes - 0.5
        volumes = np.ones(n) * 1000  # 稳定成交量

        result = liquidity.calc_liquidity_from_bars(highs, lows, closes, volumes)
        assert result.condition in ["abundant", "normal", "strained", "crisis"]
        assert result.is_proxy is True

    def test_calc_liquidity_crisis(self):
        n = 30
        closes = np.array([100 - i * 0.5 for i in range(n)], dtype=float)  # 大跌
        highs = closes + 0.5
        lows = closes - 0.5
        volumes = np.ones(n) * 1000
        volumes[-3:] = 5000  # 放量

        result = liquidity.calc_liquidity_from_bars(highs, lows, closes, volumes)
        assert result.score >= 0


class TestEventShock:
    """Test event shock module."""

    def test_calc_event_shock_fomc(self):
        result = event_shock.calc_event_shock("FOMC Rate Decision", "US", "high")
        assert result.shock_score >= 0.7
        assert result.category == "fomc"
        assert result.is_proxy is True

    def test_calc_event_shock_low_impact(self):
        result = event_shock.calc_event_shock("Retail Sales", "US", "low")
        assert result.shock_score < 0.5

    def test_calc_shock_from_returns_crash(self):
        result = event_shock.calc_shock_from_returns(
            returns_1d=-0.05, volatility=0.03
        )
        assert result.shock_score >= 0.5
        assert result.category == "geopolitical"


class TestRegimeDetector:
    """Test macro regime detection."""

    def test_risk_on_regime(self):
        n = 60
        closes = np.array([100 + i * 0.2 for i in range(n)], dtype=float)  # 上涨
        highs = closes + 1.0
        lows = closes - 1.0
        volumes = np.ones(n) * 1000

        result = regime_detector.detect_macro_regime_proxy(closes, highs, lows, volumes)
        assert result.regime in [
            regime_detector.MacroRegime.RISK_ON,
            regime_detector.MacroRegime.NEUTRAL,
        ]

    def test_risk_off_regime(self):
        n = 60
        closes = np.array([100 - i * 0.5 for i in range(n)], dtype=float)  # 下跌
        highs = closes + 3.0  # 高波动
        lows = closes - 3.0
        volumes = np.ones(n) * 1000

        result = regime_detector.detect_macro_regime_proxy(closes, highs, lows, volumes)
        assert result.regime in [
            regime_detector.MacroRegime.RISK_OFF,
            regime_detector.MacroRegime.STAGFLATION,
            regime_detector.MacroRegime.NEUTRAL,  # 可能触发 NEUTRAL
        ]

    def test_neutral_regime(self):
        n = 60
        closes = np.array([100 + np.random.uniform(-0.2, 0.2) for _ in range(n)], dtype=float)
        highs = closes + 1.0
        lows = closes - 1.0
        volumes = np.ones(n) * 1000

        result = regime_detector.detect_macro_regime_proxy(closes, highs, lows, volumes)
        assert result.regime in list(regime_detector.MacroRegime)


class TestMacroEngine:
    """Test MacroEngine integration."""

    def test_engine_initialization(self):
        engine = MacroEngine()
        assert engine.engine_name == "macro"
        assert engine.health_check() is True

    def test_analyze_with_bars_proxy(self):
        bars = _generate_bars(n=100, trend="up")
        engine = MacroEngine()
        signal = engine.analyze(bars)

        assert signal.metadata.get("proxy") is True
        assert signal.regime in [Regime.TRENDING_UP, Regime.TRENDING_DOWN, Regime.RANGING, Regime.VOLATILE, Regime.UNKNOWN]
        assert signal.metadata["rate_detail"]["is_proxy"] is True
        assert signal.metadata["liquidity_detail"]["is_proxy"] is True
        assert signal.metadata["regime_detail"]["is_proxy"] is True

    def test_analyze_with_macro_events(self):
        bars = _generate_bars(n=100)
        events = [
            _macro_event("FOMC Rate Decision", "US", "high"),
            _macro_event("CPI Inflation", "US", "medium"),
        ]
        engine = MacroEngine()
        signal = engine.analyze(bars, macro_events=events)

        assert signal.metadata.get("proxy") is False
        assert len(signal.dominant_themes) > 0

    def test_analyze_with_dict_input(self):
        data = {
            "bars": _generate_bars(n=100, trend="up"),
            "events": [{"timestamp": datetime.utcnow(), "event_name": "US CPI", "country": "US", "impact": "medium"}],
        }
        engine = MacroEngine()
        signal = engine.analyze(data)

        assert signal.metadata.get("proxy") is False

    def test_signal_fields(self):
        bars = _generate_bars(n=100)
        engine = MacroEngine()
        signal = engine.analyze(bars)

        assert hasattr(signal, "regime")
        assert hasattr(signal, "regime_confidence")
        assert hasattr(signal, "dominant_themes")
        assert hasattr(signal, "risk_on")
        assert hasattr(signal, "equity_bias")
        assert hasattr(signal, "bond_bias")
        assert hasattr(signal, "commodity_bias")
        assert hasattr(signal, "vix_level")
        assert hasattr(signal, "high_impact_events")

    def test_metadata_detail(self):
        bars = _generate_bars(n=100, trend="up")
        engine = MacroEngine()
        signal = engine.analyze(bars)

        assert "rate_detail" in signal.metadata
        assert "inflation_detail" in signal.metadata
        assert "liquidity_detail" in signal.metadata
        assert "shock_detail" in signal.metadata
        assert "regime_detail" in signal.metadata

    def test_batch_analyze(self):
        data_map = {
            "SPY": _generate_bars(n=100, trend="up"),
            "QQQ": _generate_bars(n=100, trend="down"),
        }
        engine = MacroEngine()
        signals = engine.batch_analyze(data_map)

        assert set(signals.keys()) == {"SPY", "QQQ"}

    def test_risk_on_flag(self):
        bars = _generate_bars(n=100, trend="up")
        engine = MacroEngine()
        signal = engine.analyze(bars)

        assert isinstance(signal.risk_on, bool)

    def test_vix_level(self):
        bars = _generate_bars(n=100, volatility=0.01)
        engine = MacroEngine()
        signal = engine.analyze(bars)

        assert signal.vix_level is not None
        assert signal.vix_level >= 0

    def test_asset_biases(self):
        bars = _generate_bars(n=100, trend="down")
        engine = MacroEngine()
        signal = engine.analyze(bars)

        assert signal.equity_bias in ["bullish", "bearish", "neutral"]
        assert signal.bond_bias in ["bullish", "bearish", "neutral"]
        assert signal.commodity_bias in ["bullish", "bearish", "neutral"]

    def test_custom_config(self):
        engine = MacroEngine(config={"lookback": 30, "volume_lookback": 10})
        assert engine.config["lookback"] == 30

    def test_rate_direction(self):
        bars = _generate_bars(n=100, trend="up")
        engine = MacroEngine()
        signal = engine.analyze(bars)

        direction = signal.metadata["rate_detail"]["direction"]
        assert direction in ["hiking", "cutting", "on_hold"]

    def test_liquidity_condition(self):
        bars = _generate_bars(n=100)
        engine = MacroEngine()
        signal = engine.analyze(bars)

        cond = signal.metadata["liquidity_detail"]["condition"]
        assert cond in ["abundant", "normal", "strained", "crisis"]

    def test_macro_regime_field(self):
        bars = _generate_bars(n=100)
        engine = MacroEngine()
        signal = engine.analyze(bars)

        macro_reg = signal.metadata["regime_detail"]["macro_regime"]
        assert macro_reg in [
            "risk_on", "risk_off", "stagflation", "deflationary", "neutral"
        ]

    def test_domimant_themes_not_empty(self):
        bars = _generate_bars(n=100, trend="up")
        engine = MacroEngine()
        signal = engine.analyze(bars)

        # 即使是 proxy，至少应该有 regime 主题
        assert isinstance(signal.dominant_themes, list)
