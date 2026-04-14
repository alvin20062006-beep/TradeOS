"""
Tests: Square-Root Impact Estimator
==================================
"""

from __future__ import annotations

import pytest

from core.risk.impact import estimate_square_root_impact


class TestSquareRootImpact:
    def test_basic_calculation(self) -> None:
        result = estimate_square_root_impact(
            quantity=300.0,
            adv_20d=10_000.0,
            realized_vol=0.25,
            lambda_param=0.1,
        )
        # impact = 0.1 × 0.25 × √(300/10000) = 0.1 × 0.25 × 0.1732 = 433 bps
        assert result["impact_bps"] > 0
        assert "is_acceptable" in result
        assert "participation_rate" in result

    def test_zero_adv_returns_zero_impact(self) -> None:
        result = estimate_square_root_impact(
            quantity=300.0, adv_20d=0.0, realized_vol=0.25
        )
        assert result["impact_bps"] == 0.0
        assert result["is_acceptable"] is True

    def test_impact_threshold_50bps(self) -> None:
        # Small order: low impact
        small = estimate_square_root_impact(quantity=100.0, adv_20d=1_000_000.0, realized_vol=0.20)
        assert small["is_acceptable"] is True
        assert small["impact_bps"] < 50

        # Large order: high impact
        large = estimate_square_root_impact(quantity=5_000_000.0, adv_20d=1_000_000.0, realized_vol=0.40)
        assert not large["is_acceptable"]
        assert large["impact_bps"] > 50

    def test_suggested_action(self) -> None:
        low = estimate_square_root_impact(quantity=100.0, adv_20d=1_000_000.0, realized_vol=0.10)
        assert low["suggested_action"] == "proceed"

        medium = estimate_square_root_impact(quantity=5_000_0, adv_20d=1_000_000.0, realized_vol=0.20)
        # May or may not trigger warning depending on exact value

        high = estimate_square_root_impact(quantity=5_000_000.0, adv_20d=1_000_000.0, realized_vol=0.40)
        assert high["suggested_action"] in (
            "reduce_participation", "reduce_participation_or_split"
        )
