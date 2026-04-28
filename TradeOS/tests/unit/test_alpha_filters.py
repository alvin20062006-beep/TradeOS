"""
Unit tests for alpha filters.
"""

import pytest
import pandas as pd
import numpy as np

from core.research.alpha.filters.schema import (
    FilterResult,
    RegulatoryFlag,
    MarketRegime,
    MarketRegimeResult,
    CompositeFilterResult,
)
from core.research.alpha.filters.financial_quality import (
    filter_roe_consistency,
    filter_revenue_growth,
    filter_cashflow_match,
    filter_financial_quality,
    filter_financial_quality_batch,
)
from core.research.alpha.filters.technical_filter import (
    filter_liquidity,
    filter_volatility,
    filter_price,
    filter_technical,
    filter_technical_batch,
)
from core.research.alpha.filters.market_regime import (
    detect_market_regime,
    detect_regime_history,
    filter_by_regime,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_price_data():
    """Sample price data."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    close = 100 * np.exp(np.cumsum(np.random.randn(60) * 0.02))
    volume = np.random.randint(1_000_000, 10_000_000, size=60)

    return pd.DataFrame({
        "symbol": "TEST",
        "timestamp": dates,
        "close": close,
        "volume": volume,
    })


@pytest.fixture
def sample_fundamental_data():
    """Sample fundamental data."""
    return pd.DataFrame({
        "symbol": "TEST",
        "timestamp": pd.date_range("2024-01-01", periods=8, freq="QE"),
        "roe": [0.15, 0.12, 0.18, 0.14, 0.16, 0.13, 0.17, 0.15],
        "revenue": [100, 110, 105, 120, 125, 130, 128, 140],
        "operating_cf": [20, 22, 18, 25, 26, 28, 27, 30],
        "net_income": [15, 18, 12, 20, 21, 22, 20, 25],
    })


# ── Schema Tests ────────────────────────────────────────────────────────────


class TestFilterSchema:
    def test_filter_result_and(self):
        r1 = FilterResult(passed=True, filter_name="f1")
        r2 = FilterResult(passed=False, filter_name="f2", reasons=["failed"])
        combined = r1 & r2

        assert combined.passed is False
        assert "failed" in combined.reasons

    def test_filter_result_or(self):
        r1 = FilterResult(passed=True, filter_name="f1")
        r2 = FilterResult(passed=False, filter_name="f2")
        combined = r1 | r2

        assert combined.passed is True

    def test_composite_filter_result(self):
        results = [
            FilterResult(passed=True, filter_name="f1"),
            FilterResult(passed=False, filter_name="f2", reasons=["r1"]),
            FilterResult(passed=False, filter_name="f3", reasons=["r2"]),
        ]
        composite = CompositeFilterResult.from_results(results)

        assert composite.passed is False
        assert set(composite.failed_filters) == {"f2", "f3"}


# ── Financial Quality Filter Tests ──────────────────────────────────────────


class TestFinancialQualityFilter:
    def test_filter_roe_consistency_pass(self, sample_fundamental_data):
        result = filter_roe_consistency(sample_fundamental_data, min_periods=4)
        assert result.passed is True
        assert len(result.reasons) == 0

    def test_filter_roe_consistency_fail(self, sample_fundamental_data):
        # All negative ROE
        df = sample_fundamental_data.copy()
        df["roe"] = -0.1
        result = filter_roe_consistency(df, min_periods=4)
        assert result.passed is False

    def test_filter_revenue_growth(self, sample_fundamental_data):
        result = filter_revenue_growth(sample_fundamental_data, min_growth=0.0)
        # Should pass if latest YoY growth is positive
        assert "latest_growth" in result.metadata

    def test_filter_cashflow_match(self, sample_fundamental_data):
        result = filter_cashflow_match(sample_fundamental_data)
        # Operating CF should be >= Net Income in this fixture
        assert result.passed is True

    def test_filter_financial_quality_composite(self, sample_fundamental_data):
        result = filter_financial_quality(sample_fundamental_data)
        assert hasattr(result, "passed")
        assert hasattr(result, "filter_results")


# ── Technical Filter Tests ───────────────────────────────────────────────────


class TestTechnicalFilter:
    def test_filter_liquidity(self, sample_price_data):
        result = filter_liquidity(
            sample_price_data,
            min_volume=500_000,
            min_avg_volume=1_000_000,
        )
        assert result.passed is True

    def test_filter_liquidity_fail(self, sample_price_data):
        result = filter_liquidity(
            sample_price_data,
            min_volume=100_000_000,  # Unrealistic threshold
        )
        assert result.passed is False

    def test_filter_volatility(self, sample_price_data):
        result = filter_volatility(
            sample_price_data,
            min_vol=0.05,
            max_vol=1.0,
        )
        assert "volatility" in result.metadata

    def test_filter_price(self, sample_price_data):
        result = filter_price(sample_price_data, min_price=1.0, max_price=1000.0)
        assert result.passed is True

    def test_filter_technical_composite(self, sample_price_data):
        result = filter_technical(
            sample_price_data,
            check_liquidity=True,
            check_volatility=True,
            check_price=True,
            liquidity_kwargs={"min_volume": 100_000},
            price_kwargs={"min_price": 1.0},
        )
        assert hasattr(result, "passed")


# ── Market Regime Tests ─────────────────────────────────────────────────────


class TestMarketRegime:
    def test_detect_market_regime(self, sample_price_data):
        result = detect_market_regime(sample_price_data)

        assert result.regime in [r.value for r in MarketRegime]
        assert 0.0 <= result.confidence <= 1.0
        assert "trend_return" in result.indicators

    def test_detect_regime_history(self, sample_price_data):
        result = detect_regime_history(sample_price_data, lookback=30, step=10)

        assert len(result) > 0
        assert "regime" in result.columns
        assert "confidence" in result.columns

    def test_filter_by_regime(self, sample_price_data):
        allowed = {MarketRegime.TREND_UP, MarketRegime.RANGE, MarketRegime.RECOVERY}
        is_allowed, result = filter_by_regime(sample_price_data, allowed_regimes=allowed)

        assert isinstance(is_allowed, bool)
        assert isinstance(result, MarketRegimeResult)
