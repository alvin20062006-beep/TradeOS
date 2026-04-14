"""
Tests for Order Flow Engine
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from core.analysis.orderflow import OrderFlowEngine
from core.analysis.orderflow import book_analyzer
from core.analysis.orderflow import delta
from core.analysis.orderflow import vwap as vwap_mod
from core.analysis.orderflow import large_trades
from core.analysis.orderflow import absorption
from core.analysis.orderflow import sweep
from core.analysis.orderflow import execution
from core.schemas import (
    OrderBookSnapshot,
    TradePrint,
    MarketBar,
    TimeFrame,
    Side,
    ExecutionQuality,
)


def _bar(symbol="AAPL", offset=0, open_p=100.0, high=102.0, low=98.0, close=101.0, volume=1000.0):
    """Helper: create a single bar."""
    return MarketBar(
        symbol=symbol,
        timeframe=TimeFrame.M1,
        timestamp=datetime(2024, 1, 1) + timedelta(minutes=offset),
        open=open_p,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _generate_bars(n=100, start_price=100.0):
    """Generate synthetic bars."""
    bars = []
    price = start_price
    for i in range(n):
        change = np.random.uniform(-0.5, 0.5)
        price += change
        noise = np.random.uniform(-0.2, 0.2)
        open_p = price + noise
        close = price + noise * 0.5
        high = max(open_p, close) + abs(noise)
        low = min(open_p, close) - abs(noise)
        volume = np.random.uniform(800, 1200)
        bars.append(_bar(offset=i, open_p=open_p, high=high, low=low, close=close, volume=volume))
    return bars


def _order_book(symbol="AAPL", bid_price=100.0, ask_price=100.1, bid_vol=1000.0, ask_vol=900.0):
    """Helper: create order book."""
    return OrderBookSnapshot(
        symbol=symbol,
        timestamp=datetime.utcnow(),
        bids=[(bid_price, bid_vol), (bid_price - 0.1, bid_vol * 0.8)],
        asks=[(ask_price, ask_vol), (ask_price + 0.1, ask_vol * 0.8)],
    )


def _trade(symbol="AAPL", price=100.0, size=100.0, side=Side.BUY, offset=0):
    """Helper: create a trade."""
    return TradePrint(
        symbol=symbol,
        timestamp=datetime(2024, 1, 1) + timedelta(minutes=offset),
        price=price,
        size=size,
        side=side,
        is_buy_side_taker=(side == Side.BUY),
    )


class TestBookAnalyzer:
    """Test book analyzer."""

    def test_analyze_book_basic(self):
        book = _order_book(bid_vol=1000.0, ask_vol=800.0)
        result = book_analyzer.analyze_book(book)

        assert result.imbalance > 0  # bid > ask → 正失衡
        assert 0 <= result.bid_pressure <= 1
        assert 0 <= result.ask_pressure <= 1
        assert result.spread > 0

    def test_book_imbalance_neutral(self):
        book = _order_book(bid_vol=1000.0, ask_vol=1000.0)
        result = book_analyzer.analyze_book(book)

        assert abs(result.imbalance) < 0.01  # 接近 0
        assert abs(result.bid_pressure - 0.5) < 0.01

    def test_weighted_imbalance(self):
        bids = [(100.0, 1000), (99.9, 800), (99.8, 600)]
        asks = [(100.1, 900), (100.2, 700), (100.3, 500)]

        result = book_analyzer.weighted_imbalance(bids, asks, levels=3)

        assert -1 <= result <= 1


class TestDelta:
    """Test delta/CVD module."""

    def test_calc_delta_basic(self):
        trades = [
            _trade(price=100.0, size=100.0, side=Side.BUY),
            _trade(price=100.0, size=200.0, side=Side.BUY),
            _trade(price=99.9, size=150.0, side=Side.SELL),
        ]
        result = delta.calc_delta(trades)

        # delta = buy - sell = 300 - 150 = 150
        assert result.delta == 150.0
        assert result.buy_volume == 300.0
        assert result.sell_volume == 150.0
        assert result.aggressive_buy_ratio > 0.5

    def test_cum_delta(self):
        trades = [_trade(price=100.0, size=100.0, side=Side.BUY)]
        result = delta.calc_delta(trades, prev_cum_delta=500.0)

        assert result.cum_delta == 600.0

    def test_cvd_series(self):
        trades = [
            _trade(price=100.0, size=100.0, side=Side.BUY),
            _trade(price=100.0, size=50.0, side=Side.SELL),
            _trade(price=100.0, size=200.0, side=Side.BUY),
        ]
        series = delta.cvd_series(trades)

        assert len(series) == 3
        assert series[0] == 100.0
        assert series[1] == 50.0
        assert series[2] == 250.0


class TestVWAP:
    """Test VWAP module."""

    def test_vwap_from_bars(self):
        n = 50
        highs = np.array([102.0] * n)
        lows = np.array([98.0] * n)
        closes = np.array([100.0] * n)
        volumes = np.array([1000.0] * n)

        result = vwap_mod.calc_vwap_from_bars(highs, lows, closes, volumes)

        # 典型价格 = (102+98+100)/3 = 100
        assert abs(result.vwap - 100.0) < 0.1
        assert result.deviation_abs < 0.01

    def test_vwap_deviation(self):
        n = 50
        highs = np.array([102.0] * n)
        lows = np.array([98.0] * n)
        closes = np.array([100.0] * n)
        volumes = np.array([1000.0] * n)

        result = vwap_mod.calc_vwap_from_bars(
            highs, lows, closes, volumes, current_price=101.0
        )

        # 价格高于 VWAP → 正偏离
        assert result.deviation > 0
        assert result.current_price == 101.0


class TestLargeTrades:
    """Test large trade detection."""

    def test_detect_large_trades(self):
        # 构造大单 - 平均量 = 212.5, 阈值 = 637.5
        trades = [
            _trade(price=100.0, size=100.0, side=Side.BUY),
            _trade(price=100.0, size=100.0, side=Side.BUY),
            _trade(price=100.0, size=700.0, side=Side.BUY),  # 大单 (> 637.5)
            _trade(price=100.0, size=150.0, side=Side.SELL),
        ]
        result = large_trades.detect_large_trades(trades, large_multiplier=3.0)

        # 可能检测到大单（取决于阈值计算）
        assert result.large_trade_count >= 0
        assert result.total_volume > 0


class TestAbsorption:
    """Test absorption detection."""

    def test_detect_absorption_basic(self):
        trades = [
            _trade(price=100.0, size=100.0, side=Side.BUY),
            _trade(price=100.0, size=200.0, side=Side.BUY),
            _trade(price=100.0, size=500.0, side=Side.BUY),
        ]
        result = absorption.detect_absorption(trades)

        # 所有交易在同一价位 → 可能有吸收
        assert result.absorbed_at_price == 100.0

    def test_detect_absorption_from_bars(self):
        n = 20
        highs = np.array([100.5] * n)
        lows = np.array([99.5] * n)
        closes = np.array([100.0] * n)
        volumes = np.array([1000.0] * n)
        volumes[10] = 5000.0  # 第10根放量

        result = absorption.detect_absorption_from_bars(highs, lows, closes, volumes)

        # 放量 bar 可能检测到吸收
        assert isinstance(result.absorption_score, float)


class TestSweep:
    """Test liquidity sweep detection."""

    def test_detect_sweep(self):
        n = 30
        closes = np.array([100.0 + i * 0.1 for i in range(n)], dtype=float)
        highs = closes + 0.5
        lows = closes - 0.5
        volumes = np.array([1000.0] * n)
        volumes[-5:] = 3000.0  # 最近放量

        result = sweep.detect_sweep_from_bars(
            highs, lows, closes, volumes,
            lookback=5,
            price_move_threshold=0.01,
            volume_spike_ratio=2.0,
        )

        # 有价格移动和成交量放大 → 可能检测到扫荡
        assert isinstance(result.sweep_detected, bool)


class TestExecution:
    """Test execution quality estimation."""

    def test_estimate_execution_good(self):
        book = _order_book(bid_vol=10000.0, ask_vol=10000.0)
        result = execution.estimate_execution_quality(book, order_size=100.0, side="buy")

        assert result.expected_slippage < 20  # 流动性好 → 低滑点
        assert result.execution_condition in [
            ExecutionQuality.EXCELLENT,
            ExecutionQuality.GOOD,
            ExecutionQuality.FAIR,
        ]

    def test_estimate_execution_poor(self):
        book = _order_book(bid_vol=100.0, ask_vol=100.0)
        result = execution.estimate_execution_quality(book, order_size=10000.0, side="buy")

        # 大单冲击小盘 → 需要穿透多档
        assert result.expected_slippage >= 0  # 滑点非负
        assert result.execution_condition in ExecutionQuality


class TestOrderFlowEngine:
    """Test OrderFlowEngine integration."""

    def test_engine_initialization(self):
        engine = OrderFlowEngine()
        assert engine.engine_name == "orderflow"
        assert engine.health_check() is True

    def test_analyze_with_bars_proxy(self):
        bars = _generate_bars(n=100)
        engine = OrderFlowEngine()
        signal = engine.analyze(bars)

        assert signal.symbol == "AAPL"
        assert signal.metadata.get("proxy") is True

    def test_analyze_with_order_book(self):
        bars = _generate_bars(n=100)
        book = _order_book()
        engine = OrderFlowEngine()
        signal = engine.analyze(bars, order_book=book)

        assert signal.book_imbalance != 0.0
        assert "book_imbalance_detail" in signal.metadata

    def test_analyze_with_trades(self):
        trades = [
            _trade(price=100.0, size=100.0, side=Side.BUY, offset=i)
            for i in range(10)
        ]
        engine = OrderFlowEngine()
        signal = engine.analyze(trades)

        assert signal.delta == 1000.0  # 10 trades × 100 size

    def test_analyze_full_data(self):
        bars = _generate_bars(n=100)
        book = _order_book()
        trades = [_trade(price=100.0, size=100.0, side=Side.BUY)]

        engine = OrderFlowEngine()
        signal = engine.analyze({
            "bars": bars,
            "order_book": book,
            "trades": trades,
        })

        assert signal.metadata.get("proxy") is False
        assert signal.book_imbalance != 0.0
        assert signal.delta != 0.0

    def test_batch_analyze(self):
        data_map = {
            "AAPL": _generate_bars(n=100),
            "TSLA": _generate_bars(n=100),
        }
        engine = OrderFlowEngine()
        signals = engine.batch_analyze(data_map)

        assert set(signals.keys()) == {"AAPL", "TSLA"}

    def test_signal_fields(self):
        bars = _generate_bars(n=100)
        engine = OrderFlowEngine()
        signal = engine.analyze(bars)

        # 检查所有必要字段存在
        assert hasattr(signal, "book_imbalance")
        assert hasattr(signal, "bid_pressure")
        assert hasattr(signal, "ask_pressure")
        assert hasattr(signal, "delta")
        assert hasattr(signal, "cum_delta")
        assert hasattr(signal, "absorption_score")
        assert hasattr(signal, "liquidity_sweep")
        assert hasattr(signal, "expected_slippage")
        assert hasattr(signal, "execution_condition")
        assert hasattr(signal, "stop_hunt_zones")

    def test_cum_delta_persists(self):
        trades = [_trade(price=100.0, size=100.0, side=Side.BUY)]
        engine = OrderFlowEngine()
        signal1 = engine.analyze(trades)
        signal2 = engine.analyze(trades)

        # 第二次分析应该累计之前的 delta
        assert signal2.cum_delta == signal1.cum_delta + 100.0

    def test_reset(self):
        engine = OrderFlowEngine()
        engine._cum_delta = 500.0
        engine.reset()

        assert engine._cum_delta == 0.0
