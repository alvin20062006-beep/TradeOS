"""
Unit tests for extended alpha builders (macro, orderflow, regulatory).
"""

import pytest
import pandas as pd
import numpy as np

from core.research.alpha.builders.macro import (
    RateDeltaBuilder,
    VolTrendBuilder,
    YieldSpreadBuilder,
    build_all_macro,
)
from core.research.alpha.builders.orderflow import (
    VWAPDeviationBuilder,
    VWAPSlopeBuilder,
    VolumeConcentrationBuilder,
    build_all_orderflow,
)
from core.research.alpha.builders.regulatory import (
    RegulatoryFlagBuilder,
    RegulatoryFlag,
    detect_regulatory_flags,
    is_tradable,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_ohlcv():
    """Sample OHLCV data for 2 symbols over 30 days."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=30, freq="D")

    frames = []
    for sym in ["AAPL", "MSFT"]:
        close = 100 * np.exp(np.cumsum(np.random.randn(30) * 0.02))
        high = close * (1 + np.abs(np.random.randn(30)) * 0.01)
        low = close * (1 - np.abs(np.random.randn(30)) * 0.01)
        volume = np.random.randint(1_000_000, 10_000_000, size=30)

        df = pd.DataFrame({
            "symbol": sym,
            "timestamp": dates,
            "close": close,
            "high": high,
            "low": low,
            "volume": volume,
        })
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


# ── Macro Builders ───────────────────────────────────────────────────────────


class TestMacroBuilders:
    def test_rate_delta_builder(self, sample_ohlcv):
        builder = RateDeltaBuilder(period=5)
        result = builder.compute(sample_ohlcv)

        assert "symbol" in result.columns
        assert "timestamp" in result.columns
        assert "raw_value" in result.columns
        assert len(result) > 0
        assert not result["raw_value"].isna().all()

    def test_vol_trend_builder(self, sample_ohlcv):
        builder = VolTrendBuilder(ma_period=10)
        result = builder.compute(sample_ohlcv)

        assert len(result) > 0
        assert "raw_value" in result.columns

    def test_yield_spread_builder(self, sample_ohlcv):
        builder = YieldSpreadBuilder(smooth_period=5)
        result = builder.compute(sample_ohlcv)

        assert len(result) > 0
        # Yield spread should be positive (high > low)
        assert (result["raw_value"] > 0).all()

    def test_build_all_macro(self, sample_ohlcv):
        result = build_all_macro(sample_ohlcv)

        assert "factor_name" in result.columns
        assert set(result["factor_name"].unique()) == {"RATE_DELTA", "VOL_TREND", "YIELD_SPREAD"}


# ── Orderflow Builders ───────────────────────────────────────────────────────


class TestOrderflowBuilders:
    def test_vwap_deviation_builder(self, sample_ohlcv):
        builder = VWAPDeviationBuilder(vwap_period=10)
        result = builder.compute(sample_ohlcv)

        assert len(result) > 0
        assert "raw_value" in result.columns

    def test_vwap_slope_builder(self, sample_ohlcv):
        builder = VWAPSlopeBuilder(vwap_period=10, slope_period=3)
        result = builder.compute(sample_ohlcv)

        assert len(result) > 0

    def test_volume_concentration_builder(self, sample_ohlcv):
        builder = VolumeConcentrationBuilder(ma_period=10)
        result = builder.compute(sample_ohlcv)

        assert len(result) > 0
        # Volume concentration can be negative (below avg) or positive (above avg)

    def test_build_all_orderflow(self, sample_ohlcv):
        result = build_all_orderflow(sample_ohlcv)

        assert "factor_name" in result.columns
        assert set(result["factor_name"].unique()) == {"VWAP_DEV", "VWAP_SLOPE", "VOL_CONCENTRATION"}


# ── Regulatory Builder ───────────────────────────────────────────────────────


class TestRegulatoryBuilder:
    def test_detect_regulatory_flags_basic(self, sample_ohlcv):
        result = detect_regulatory_flags(sample_ohlcv)

        assert "symbol" in result.columns
        assert "timestamp" in result.columns
        assert "flags" in result.columns

    def test_detect_limit_up_down(self):
        """Test limit up/down detection."""
        df = pd.DataFrame({
            "symbol": "TEST",
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="D"),
            "close": [100, 110, 99],  # +10% then -10%
        })
        result = detect_regulatory_flags(df, limit_threshold=0.09)

        # Day 2 should have limit_up flag
        assert RegulatoryFlag.LIMIT_UP in result.iloc[1]["flags"]
        # Day 3 should have limit_down flag
        assert RegulatoryFlag.LIMIT_DOWN in result.iloc[2]["flags"]

    def test_detect_st_symbols(self):
        df = pd.DataFrame({
            "symbol": ["ST001", "NORMAL", "*ST002"],
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="D"),
            "close": [10, 20, 15],
        })
        result = detect_regulatory_flags(
            df,
            st_symbols={"ST", "*ST"},
        )

        assert RegulatoryFlag.ST in result.iloc[0]["flags"]
        assert RegulatoryFlag.ST not in result.iloc[1]["flags"]
        assert RegulatoryFlag.ST in result.iloc[2]["flags"]

    def test_is_tradable(self, sample_ohlcv):
        result = detect_regulatory_flags(sample_ohlcv)
        tradable = is_tradable(result)

        assert tradable.dtype == bool
        assert len(tradable) == len(result)

    def test_filter_tradable(self):
        df = pd.DataFrame({
            "symbol": "TEST",
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="D"),
            "close": [100, 110, 100],  # Day 2 hits limit
        })
        builder = RegulatoryFlagBuilder(limit_threshold=0.09)
        flags = builder.compute(df)
        tradable = builder.filter_tradable(flags)

        # Day 1 and 3 should be tradable (no limit flag)
        # Day 2 has limit_up flag due to +10% change
        assert len(tradable) >= 1  # At least day 1 is tradable
