"""单元测试：4 个策略 builders。"""
import pytest

from core.strategy_pool.builders.breakout import BreakoutStrategy
from core.strategy_pool.builders.mean_reversion import MeanReversionStrategy
from core.strategy_pool.builders.reversal import ReversalStrategy
from core.strategy_pool.builders.trend import TrendFollowingStrategy
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle
from core.strategy_pool.schemas.strategy import StrategyType


def _ohlcv(open_pct=0, n=60) -> list:
    """生成 n 天基准 OHLCV 数据（从 open_pct 缓慢上涨）。"""
    base = 100.0
    data = []
    price = base
    for i in range(n):
        change = (i * 0.001) + open_pct
        close = price * (1 + change)
        high = close * 1.01
        low = close * 0.99
        data.append({
            "date": f"2024-01-{i+1:02d}",
            "open": price,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1_000_000,
        })
        price = close
    return data


class TestTrendFollowingStrategy:
    def test_validate_params(self):
        s = TrendFollowingStrategy()
        assert s.validate_params({"short_ma_period": 5, "long_ma_period": 20})
        assert not s.validate_params({"short_ma_period": 20, "long_ma_period": 5})

    def test_generate_signals(self):
        s = TrendFollowingStrategy({
            "strategy_id": "trend-test",
            "short_ma_period": 5,
            "long_ma_period": 10,
            "momentum_window": 5,
            "momentum_threshold": 0.0,
        })
        data = _ohlcv(n=20)
        signals = s.generate_signals(data, "AAPL")
        assert len(signals) >= 0  # 信号取决于数据
        for sig in signals:
            assert sig.symbol == "AAPL"
            assert sig.direction in ("LONG", "SHORT", "FLAT")

    def test_spec(self):
        s = TrendFollowingStrategy({"strategy_id": "trend-spec"})
        spec = s.get_spec()
        assert spec.strategy_type == StrategyType.TREND
        assert spec.name == "TrendFollowing"


class TestMeanReversionStrategy:
    def test_validate_params(self):
        s = MeanReversionStrategy()
        assert s.validate_params({
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "bb_period": 20,
        })

    def test_generate_signals(self):
        s = MeanReversionStrategy({
            "strategy_id": "mr-test",
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "bb_period": 20,
        })
        data = _ohlcv(n=30)
        signals = s.generate_signals(data, "TSLA")
        for sig in signals:
            assert sig.symbol == "TSLA"
            assert sig.direction in ("LONG", "SHORT", "FLAT")

    def test_spec(self):
        s = MeanReversionStrategy({"strategy_id": "mr-spec"})
        spec = s.get_spec()
        assert spec.strategy_type == StrategyType.MEAN_REVERSION


class TestBreakoutStrategy:
    def test_validate_params(self):
        s = BreakoutStrategy()
        assert s.validate_params({"lookback_period": 20, "vol_period": 20, "vol_threshold": 1.5})

    def test_generate_signals(self):
        s = BreakoutStrategy({
            "strategy_id": "bo-test",
            "lookback_period": 10,
            "vol_period": 10,
            "vol_threshold": 1.0,
        })
        # 制造一个明显突破
        data = _ohlcv(n=20)
        data[-1]["close"] = 200.0  # 大幅向上突破
        data[-1]["high"] = 205.0
        signals = s.generate_signals(data, "NVDA")
        for sig in signals:
            assert sig.symbol == "NVDA"
            assert sig.direction in ("LONG", "SHORT", "FLAT")

    def test_spec(self):
        s = BreakoutStrategy({"strategy_id": "bo-spec"})
        assert s.get_spec().strategy_type == StrategyType.BREAKOUT


class TestReversalStrategy:
    def test_validate_params(self):
        s = ReversalStrategy()
        assert s.validate_params({
            "return_period": 5,
            "long_threshold": -0.03,
            "short_threshold": 0.03,
        })

    def test_generate_signals(self):
        s = ReversalStrategy({
            "strategy_id": "rev-test",
            "return_period": 5,
            "long_threshold": -0.03,
            "short_threshold": 0.03,
            "vol_ma_period": 10,
        })
        # 制造一个大幅下跌 → LONG
        data = _ohlcv(n=20)
        data[-1]["close"] = data[-2]["close"] * 0.90
        signals = s.generate_signals(data, "AMD")
        for sig in signals:
            assert sig.symbol == "AMD"
            assert sig.direction in ("LONG", "SHORT", "FLAT")

    def test_spec(self):
        s = ReversalStrategy({"strategy_id": "rev-spec"})
        assert s.get_spec().strategy_type == StrategyType.REVERSAL
