"""
Tests: Position Calculators
========================
"""

from __future__ import annotations

import pytest

from core.risk.calculators import (
    ConvictionWeightedCalculator,
    DrawdownAdjustedCalculator,
    FixedFractionCalculator,
    KellyFractionCalculator,
    RegimeBasedCalculator,
    VolatilityTargetingCalculator,
)
from core.risk.context import MarketContext


def _ctx(
    price: float = 100.0,
    adv: float = 1_000_000.0,
    realized_vol: float = 0.20,
    atr: float = 2.0,
) -> MarketContext:
    return MarketContext(
        symbol="AAPL",
        timestamp=None,
        current_price=price,
        avg_daily_volume_20d=adv,
        realized_vol_20d=realized_vol,
        atr_14=atr,
    )


class TestVolatilityTargeting:
    def test_basic_calculation(self) -> None:
        calc = VolatilityTargetingCalculator()
        ctx = _ctx(price=200.0, realized_vol=0.25)
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.8,
            direction_sign=1,
            market_context=ctx,
            target_annual_vol=0.15,
        )
        assert result["qty"] > 0
        assert result["method"] == "volatility_targeting"
        assert result["confidence"] > 0

    def test_zero_vol_returns_zero(self) -> None:
        calc = VolatilityTargetingCalculator()
        ctx = _ctx(realized_vol=0.0)
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.5,
            direction_sign=1,
            market_context=ctx,
        )
        assert result["qty"] == 0.0


class TestKellyFraction:
    def test_kelly_with_history(self) -> None:
        calc = KellyFractionCalculator()
        ctx = _ctx(price=100.0)
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.8,
            direction_sign=1,
            market_context=ctx,
            kelly_win_rate=0.55,
            kelly_avg_win=100.0,
            kelly_avg_loss=80.0,
        )
        assert result["qty"] > 0
        assert result["method"] == "kelly"

    def test_kelly_without_history_returns_zero(self) -> None:
        calc = KellyFractionCalculator()
        ctx = _ctx()
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.8,
            direction_sign=1,
            market_context=ctx,
        )
        assert result["qty"] == 0.0


class TestFixedFraction:
    def test_basic(self) -> None:
        calc = FixedFractionCalculator()
        ctx = _ctx(price=100.0, atr=2.0)
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.5,
            direction_sign=1,
            market_context=ctx,
            stop_distance_pct=0.02,
        )
        assert result["qty"] > 0
        assert result["method"] == "fixed_fraction"


class TestConvictionWeighted:
    def test_confidence_affects_qty(self) -> None:
        calc = ConvictionWeightedCalculator()
        ctx = _ctx()
        high = calc.calculate(100_000.0, 0.9, 1, ctx)
        low = calc.calculate(100_000.0, 0.3, 1, ctx)
        assert high["qty"] > low["qty"]


class TestDrawdownAdjusted:
    def test_no_drawdown_full_size(self) -> None:
        calc = DrawdownAdjustedCalculator()
        ctx = _ctx()
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.8,
            direction_sign=1,
            market_context=ctx,
            drawdown_ratio=0.0,
        )
        assert result["qty"] > 0

    def test_high_drawdown_zero_size(self) -> None:
        calc = DrawdownAdjustedCalculator()
        ctx = _ctx()
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.8,
            direction_sign=1,
            market_context=ctx,
            drawdown_ratio=1.0,
        )
        assert result["qty"] == 0.0


class TestRegimeBased:
    def test_trending_up_increases_size(self) -> None:
        calc = RegimeBasedCalculator()
        ctx = _ctx()
        # 直接调用子类方法（有 regime_name 参数）
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.8,
            direction_sign=1,
            market_context=ctx,
            regime_name="trending_up",
        )
        assert result["qty"] > 0

    def test_volatile_reduces_size(self) -> None:
        calc = RegimeBasedCalculator()
        from core.risk.context import MarketContext
        ctx = MarketContext(symbol="A", timestamp=None, current_price=100.0)
        result = calc.calculate(
            portfolio_equity=100_000.0,
            direction_confidence=0.8,
            direction_sign=1,
            market_context=ctx,
            regime_name="volatile",
        )
        # volatile: base_qty=50, confidence=0.8, multiplier=0.5 → qty=40, conf=0.4
        # ranging:   base_qty=50, confidence=0.8, multiplier=1.0 → qty=50, conf=0.8
        assert result["qty"] == 40.0
        assert result["qty"] < 50.0  # 严格小于 ranging
        assert result["method"] == "regime_based"
