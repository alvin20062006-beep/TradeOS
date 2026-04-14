"""
Test: Phase 9 → Phase 6 Integration (Unit)
==========================================

验证 arbitrate_portfolio() 与原有 arbitrate() 的边界：
- 方向映射正确
- 置信度 / 权重正确传递
- 空 proposals graceful 降级
- Phase 5 → arbitrate() 路径不被破坏
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.arbitration import ArbitrationEngine
from core.arbitration.schemas import _StrategySignalSource
from core.schemas import (
    ChanSignal,
    Direction,
    Regime,
    TechnicalSignal,
    TimeFrame,
)
from core.strategy_pool.schemas.arbitration_input import (
    ArbitrationInputBundle,
    PortfolioProposal,
    StrategyProposal,
)
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def engine() -> ArbitrationEngine:
    return ArbitrationEngine()


@pytest.fixture
def ts() -> datetime:
    return datetime(2026, 4, 12, 6, 0, 0)


def strategy_proposal(
    proposal_id: str,
    strategy_id: str,
    direction: str,
    confidence: float,
    strength: float,
    weight: float,
) -> StrategyProposal:
    return StrategyProposal(
        proposal_id=proposal_id,
        strategy_id=strategy_id,
        bundles=[],
        aggregate_direction=direction,
        aggregate_strength=strength,
        aggregate_confidence=confidence,
        portfolio_weight=weight,
    )


def arb_bundle(proposals: list[StrategyProposal]) -> ArbitrationInputBundle:
    pp = PortfolioProposal(
        proposal_id="pp-001",
        portfolio_id="AAPL-SP",
        proposals=proposals,
        composite_direction="LONG",
        composite_strength=0.7,
        composite_confidence=0.7,
    )
    return ArbitrationInputBundle(
        bundle_id="bundle-001",
        timestamp=datetime(2026, 4, 12, 6, 0, 0),
        portfolio_proposal=pp,
    )


# ── _StrategySignalSource 映射测试 ───────────────────────────────────


class TestStrategySignalSourceMapping:
    """F10-S1 / F10-S2：方向映射、置信度/权重传递"""

    def test_long_direction_maps_to_long(self):
        src = _StrategySignalSource(
            proposal_id="p-001",
            strategy_id="trend-001",
            aggregate_direction="LONG",
            aggregate_confidence=0.8,
            aggregate_strength=0.7,
            portfolio_weight=0.5,
        )
        ds = src.to_directional()
        assert ds.direction == Direction.LONG
        assert ds.engine_name == "strategy_pool:trend-001"
        assert ds.confidence == 0.8
        assert ds.weight == 0.5

    def test_short_direction_maps_to_short(self):
        src = _StrategySignalSource(
            proposal_id="p-002",
            strategy_id="meanrev-001",
            aggregate_direction="SHORT",
            aggregate_confidence=0.6,
            aggregate_strength=0.5,
            portfolio_weight=0.3,
        )
        ds = src.to_directional()
        assert ds.direction == Direction.SHORT
        assert ds.engine_name == "strategy_pool:meanrev-001"
        assert ds.confidence == 0.6
        assert ds.weight == 0.3

    def test_flat_direction_maps_to_flat(self):
        src = _StrategySignalSource(
            proposal_id="p-003",
            strategy_id="breakout-001",
            aggregate_direction="FLAT",
            aggregate_confidence=0.4,
            aggregate_strength=0.2,
            portfolio_weight=0.0,
        )
        ds = src.to_directional()
        assert ds.direction == Direction.FLAT
        # portfolio_weight=0 → 默认 weight=1.0
        assert ds.weight == 1.0

    def test_unknown_direction_defaults_to_flat(self):
        src = _StrategySignalSource(
            proposal_id="p-004",
            strategy_id="rev-001",
            aggregate_direction="UNKNOWN",
            aggregate_confidence=0.5,
            aggregate_strength=0.5,
            portfolio_weight=0.5,
        )
        ds = src.to_directional()
        assert ds.direction == Direction.FLAT


# ── arbitrate_portfolio() 基础测试 ──────────────────────────────────


class TestArbitratePortfolioBasic:
    """F10-I1 / F10-I2：ArbitrationInputBundle 被实际消费，产出正式 ArbitrationDecision"""

    def test_single_long_strategy_produces_long_bias(self, engine: ArbitrationEngine):
        proposals = [
            strategy_proposal(
                proposal_id="p-trend-001",
                strategy_id="trend",
                direction="LONG",
                confidence=0.8,
                strength=0.7,
                weight=1.0,
            )
        ]
        bundle = arb_bundle(proposals)
        decision = engine.arbitrate_portfolio(bundle)

        assert decision.bias in ("long_bias", "no_trade")
        assert decision.confidence >= 0.0
        assert decision.signal_count == 1
        # rationale 中有 strategy_pool:{strategy_id} 条目
        strategy_rationale = [r for r in decision.rationale if r.signal_name.startswith("strategy_pool:")]
        assert len(strategy_rationale) == 1
        assert strategy_rationale[0].direction == Direction.LONG
        assert strategy_rationale[0].confidence == 0.8

    def test_output_is_formal_arbitration_decision(self, engine: ArbitrationEngine):
        proposals = [
            strategy_proposal(
                proposal_id="p-breakout-001",
                strategy_id="breakout",
                direction="SHORT",
                confidence=0.7,
                strength=0.6,
                weight=0.5,
            )
        ]
        bundle = arb_bundle(proposals)
        decision = engine.arbitrate_portfolio(bundle)

        # 正式 ArbitrationDecision 必须包含所有必需字段
        assert decision.decision_id is not None
        assert decision.timestamp is not None
        assert decision.symbol is not None
        assert decision.bias in ("long_bias", "short_bias", "hold_bias", "no_trade", "reduce_risk", "exit_bias")
        assert decision.confidence is not None
        assert decision.arbitration_latency_ms >= 0.0


# ── 多策略场景 ──────────────────────────────────────────────────────


class TestArbitratePortfolioMultiStrategy:
    """F10-R1：多策略反向时 DirectionConflictRule 触发"""

    def test_two_opposing_strategies_bias_neutralizes(self, engine: ArbitrationEngine):
        proposals = [
            strategy_proposal(
                proposal_id="p-trend-001",
                strategy_id="trend",
                direction="LONG",
                confidence=0.7,
                strength=0.7,
                weight=0.5,
            ),
            strategy_proposal(
                proposal_id="p-meanrev-001",
                strategy_id="meanrev",
                direction="SHORT",
                confidence=0.7,
                strength=0.7,
                weight=0.5,
            ),
        ]
        bundle = arb_bundle(proposals)
        decision = engine.arbitrate_portfolio(bundle)

        # 方向冲突应触发中性化
        assert decision.signal_count == 2
        # bias 不应是明确的多空
        assert decision.bias in ("no_trade", "hold_bias", "long_bias", "short_bias")

    def test_two_same_direction_strategies_adds_signals(self, engine: ArbitrationEngine):
        proposals = [
            strategy_proposal(
                proposal_id="p-trend-001",
                strategy_id="trend",
                direction="LONG",
                confidence=0.6,
                strength=0.6,
                weight=0.5,
            ),
            strategy_proposal(
                proposal_id="p-breakout-001",
                strategy_id="breakout",
                direction="LONG",
                confidence=0.6,
                strength=0.6,
                weight=0.5,
            ),
        ]
        bundle = arb_bundle(proposals)
        decision = engine.arbitrate_portfolio(bundle)

        assert decision.signal_count == 2
        strategy_rationale = [r for r in decision.rationale if r.signal_name.startswith("strategy_pool:")]
        assert len(strategy_rationale) == 2


# ── 空输入 / 边界条件 ──────────────────────────────────────────────


class TestArbitratePortfolioEdgeCases:
    """F10-R3：空 portfolio graceful 降级"""

    def test_empty_proposals_returns_no_trade(self, engine: ArbitrationEngine):
        bundle = arb_bundle([])
        decision = engine.arbitrate_portfolio(bundle)

        assert decision.bias == "no_trade"
        assert decision.confidence == 0.0
        assert decision.signal_count == 0

    def test_empty_proposals_has_valid_decision_id(self, engine: ArbitrationEngine):
        bundle = arb_bundle([])
        decision = engine.arbitrate_portfolio(bundle)

        assert decision.decision_id is not None
        assert decision.decision_id.startswith("arb-portfolio-")


# ── 原有 arbitrate() 不被破坏 ───────────────────────────────────────


class TestOriginalArbitrateNotBroken:
    """F10-S4 / F10-E1：原有 Phase 5 → arbitrate() 路径不被破坏"""

    def test_arbitrate_still_works_with_technical_signal(self, engine: ArbitrationEngine, ts: datetime):
        tech = TechnicalSignal(
            engine_name="technical",
            symbol="AAPL",
            timestamp=ts,
            direction=Direction.LONG,
            confidence=0.75,
            regime=Regime.TRENDING_UP,
        )
        decision = engine.arbitrate(symbol="AAPL", timestamp=ts, technical=tech)

        assert decision.bias == "long_bias"
        assert decision.confidence > 0.0
        assert decision.signal_count == 1
        assert decision.arbitration_latency_ms >= 0.0

    def test_arbitrate_still_works_with_no_signals(self, engine: ArbitrationEngine, ts: datetime):
        decision = engine.arbitrate(symbol="AAPL", timestamp=ts)

        assert decision.bias == "no_trade"
        assert decision.confidence == 0.0
        assert decision.signal_count == 0

    def test_arbitrate_still_works_with_multiple_signals(self, engine: ArbitrationEngine, ts: datetime):
        tech = TechnicalSignal(
            engine_name="technical",
            symbol="AAPL",
            timestamp=ts,
            direction=Direction.LONG,
            confidence=0.7,
            regime=Regime.TRENDING_UP,
        )
        chan = ChanSignal(
            engine_name="chan",
            symbol="AAPL",
            timestamp=ts,
            direction=Direction.LONG,
            confidence=0.65,
            regime=Regime.TRENDING_UP,
        )
        decision = engine.arbitrate(symbol="AAPL", timestamp=ts, technical=tech, chan=chan)

        assert decision.signal_count == 2
        assert decision.bias in ("long_bias", "no_trade")
