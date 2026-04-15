"""单元测试：策略 Schema。"""
import tempfile
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.strategy_pool.schemas.arbitration_input import (
    ArbitrationInputBundle,
    PortfolioProposal,
    StrategyProposal,
)
from core.strategy_pool.schemas.portfolio import StrategyPortfolio, StrategyWeight
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle
from core.strategy_pool.schemas.strategy import StrategySpec, StrategyStatus, StrategyType


class TestStrategySpec:
    def test_minimal_create(self):
        spec = StrategySpec(
            strategy_id="s1",
            name="Test",
            strategy_type=StrategyType.TREND,
        )
        assert spec.strategy_id == "s1"
        assert spec.status == StrategyStatus.CANDIDATE
        assert spec.version == 1

    def test_full_create(self):
        spec = StrategySpec(
            strategy_id="s2",
            name="Trend AAPL",
            strategy_type=StrategyType.TREND,
            bias="long_bias",
            direction="LONG",
            params={"ma_period": 20},
            lookback=20,
            max_position_pct=0.15,
            stop_loss_pct=0.03,
            target_return_pct=0.10,
        )
        assert spec.bias == "long_bias"
        assert spec.direction == "LONG"
        assert spec.params["ma_period"] == 20
        assert spec.max_position_pct == 0.15

    def test_invalid_direction(self):
        with pytest.raises(ValidationError):
            StrategySpec(
                strategy_id="s3",
                name="Bad",
                strategy_type=StrategyType.MEAN_REVERSION,
                direction="INVALID",
            )

    def test_invalid_max_position(self):
        with pytest.raises(ValidationError):
            StrategySpec(
                strategy_id="s4",
                name="Bad2",
                strategy_type=StrategyType.BREAKOUT,
                max_position_pct=1.5,
            )


class TestSignalBundle:
    def test_minimal_create(self):
        bundle = StrategySignalBundle(
            bundle_id="b1",
            source_strategy_id="s1",
            symbol="AAPL",
            direction="LONG",
        )
        assert bundle.direction == "LONG"
        assert bundle.strength == 0.0
        assert bundle.confidence == 0.5
        assert bundle.supporting_signals == []

    def test_full_create(self):
        bundle = StrategySignalBundle(
            bundle_id="b2",
            source_strategy_id="trend1",
            symbol="TSLA",
            direction="SHORT",
            strength=0.85,
            confidence=0.75,
            supporting_signals=["sig-001"],
            supporting_snapshots=["alpha-042"],
            metadata={"ma_cross": True},
        )
        assert bundle.strength == 0.85
        assert bundle.supporting_snapshots == ["alpha-042"]

    def test_invalid_strength(self):
        with pytest.raises(ValidationError):
            StrategySignalBundle(
                bundle_id="b3",
                source_strategy_id="s1",
                symbol="AAPL",
                direction="LONG",
                strength=1.5,
            )


class TestStrategyPortfolio:
    def test_minimal_create(self):
        portfolio = StrategyPortfolio(
            portfolio_id="p1",
            name="My Portfolio",
        )
        assert portfolio.status == StrategyStatus.CANDIDATE
        assert portfolio.rebalance_frequency == "daily"

    def test_strategy_weights(self):
        sw = StrategyWeight(strategy_id="s1", weight=0.4, weight_method="equal")
        assert sw.weight == 0.4
        assert sw.weight_method == "equal"

        portfolio = StrategyPortfolio(
            portfolio_id="p2",
            name="Weighted",
            strategy_weights=[sw],
        )
        assert len(portfolio.strategy_weights) == 1
        assert portfolio.strategy_weights[0].strategy_id == "s1"


class TestArbitrationInput:
    def test_strategy_proposal(self):
        bundle = StrategySignalBundle(
            bundle_id="b1",
            source_strategy_id="s1",
            symbol="AAPL",
            direction="LONG",
            strength=0.8,
            confidence=0.7,
        )
        prop = StrategyProposal(
            proposal_id="prop1",
            strategy_id="s1",
            bundles=[bundle],
            aggregate_direction="LONG",
            aggregate_strength=0.8,
            aggregate_confidence=0.7,
            portfolio_weight=0.5,
        )
        assert prop.aggregate_direction == "LONG"
        assert len(prop.bundles) == 1

    def test_portfolio_proposal(self):
        pp = PortfolioProposal(
            proposal_id="pp1",
            portfolio_id="port1",
            proposals=[],
            composite_direction="LONG",
            composite_strength=0.6,
            composite_confidence=0.55,
            weight_method="equal",
        )
        assert pp.composite_direction == "LONG"

    def test_arbitration_input_bundle(self):
        bundle = ArbitrationInputBundle(
            bundle_id="aib1",
            portfolio_proposal=PortfolioProposal(
                proposal_id="pp1",
                portfolio_id="port1",
                proposals=[],
                composite_direction="FLAT",
                composite_strength=0.0,
                composite_confidence=0.0,
            ),
            supporting_factor_ids=["alpha-001", "alpha-002"],
            regime_context={"regime": "trending"},
        )
        assert len(bundle.supporting_factor_ids) == 2
        assert bundle.regime_context["regime"] == "trending"
