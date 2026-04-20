"""
Tests: Risk Filters
==================
"""

from __future__ import annotations

import pytest

from core.risk.context import MarketContext
from core.risk.filters import (
    CorrelationLimitFilter,
    LiquidityCapFilter,
    LossLimitFilter,
    ParticipationRateFilter,
    PositionLimitFilter,
)
from core.risk.filters.base import RiskFilter
from core.schemas import RiskLimits


def _ctx(price=100.0, adv=1_000_000.0) -> MarketContext:
    return MarketContext(
        symbol="AAPL",
        timestamp=None,
        current_price=price,
        avg_daily_volume_20d=adv,
        realized_vol_20d=0.20,
    )


class TestPositionLimitFilter:
    def setup_method(self) -> None:
        self.f = PositionLimitFilter()

    def test_under_limit_passes(self) -> None:
        limits = RiskLimits(max_position_pct=0.10)
        result = self.f.apply(
            qty=50.0, direction_sign=1,
            portfolio_equity=100_000.0, current_price=100.0,
            risk_limits=limits,
        )
        assert result.passed
        assert result.adjusted_qty == 50.0

    def test_over_limit_capped(self) -> None:
        limits = RiskLimits(max_position_pct=0.05)
        result = self.f.apply(
            qty=100.0, direction_sign=1,
            portfolio_equity=100_000.0, current_price=100.0,
            risk_limits=limits,
        )
        # capping = adjust, not reject → passed=True
        assert result.passed
        assert result.adjusted_qty < 100.0  # 已被打压
        assert result.adjusted_qty == 50.0  # 5% × $100,000 / $100


class TestLossLimitFilter:
    def setup_method(self) -> None:
        self.f = LossLimitFilter()

    def test_under_loss_limit_passes(self) -> None:
        limits = RiskLimits(max_loss_pct_per_trade=0.05)
        result = self.f.apply(
            qty=100.0, direction_sign=1,
            portfolio_equity=100_000.0, current_price=100.0,
            avg_entry_price=100.0,
            risk_limits=limits,
        )
        assert result.passed

    def test_over_daily_loss_veto(self) -> None:
        limits = RiskLimits(max_loss_pct_per_day=0.03)
        result = self.f.apply(
            qty=10.0, direction_sign=1,
            portfolio_equity=100_000.0, current_price=100.0,
            daily_loss_pct=0.05,
            risk_limits=limits,
        )
        assert not result.passed
        assert result.adjusted_qty == 0.0


class TestLiquidityCapFilter:
    def setup_method(self) -> None:
        self.f = LiquidityCapFilter()

    def test_qty_under_adv_cap(self) -> None:
        ctx = _ctx(adv=1_000_000.0)
        result = self.f.apply(
            qty=50_000.0, direction_sign=1,
            market_context=ctx,
        )
        # 50k / 1M ADV = 5% < 20% cap
        assert result.passed

    def test_qty_over_adv_cap_capped(self) -> None:
        ctx = _ctx(adv=1_000_000.0)
        result = self.f.apply(
            qty=400_000.0, direction_sign=1,
            market_context=ctx,
        )
        # cap = adjust, not reject → passed=True, mode="cap"
        assert result.passed
        assert result.mode == "cap"
        assert result.adjusted_qty == 200_000.0


class TestParticipationRateFilter:
    def setup_method(self) -> None:
        self.f = ParticipationRateFilter()

    def test_under_limit_passes(self) -> None:
        ctx = MarketContext(
            symbol="AAPL", timestamp=None,
            current_price=100.0,
            avg_daily_volume_20d=1_000_000.0,
            adv_20d_usd=100_000_000.0,
        )
        result = self.f.apply(
            qty=50_000.0, direction_sign=1,
            market_context=ctx,
            urgency="medium",
        )
        # 50k × $100 = $5M notional / $100M ADV = 5% ≤ 10%
        assert result.passed

    def test_over_limit_capped(self) -> None:
        ctx = MarketContext(
            symbol="AAPL", timestamp=None,
            current_price=100.0,
            avg_daily_volume_20d=1_000_000.0,
            adv_20d_usd=100_000_000.0,
        )
        result = self.f.apply(
            qty=500_000.0, direction_sign=1,
            market_context=ctx,
            urgency="medium",
        )
        # cap = adjust, not reject → passed=True, mode="cap"
        assert result.passed
        assert result.mode == "cap"
        assert result.adjusted_qty < 500_000.0


class TestCorrelationLimitFilter:
    def setup_method(self) -> None:
        self.f = CorrelationLimitFilter()

    def test_correlation_under_limit_passes(self) -> None:
        limits = RiskLimits(max_correlation=0.70)
        result = self.f.apply(
            qty=100.0,
            direction_sign=1,
            symbol="AAPL",
            existing_position_symbols=["MSFT"],
            existing_directions=[1],
            correlation_value=0.45,
            risk_limits=limits,
        )
        assert result.passed
        assert result.mode == "pass"
        assert result.adjusted_qty == 100.0

    def test_correlation_over_limit_reduces_qty(self) -> None:
        limits = RiskLimits(max_correlation=0.60)
        result = self.f.apply(
            qty=100.0,
            direction_sign=1,
            symbol="AAPL",
            existing_position_symbols=["MSFT"],
            existing_directions=[1],
            correlation_value=0.92,
            risk_limits=limits,
        )
        assert result.passed
        assert result.mode == "cap"
        assert result.adjusted_qty < 100.0
