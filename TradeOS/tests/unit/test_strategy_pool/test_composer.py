"""单元测试：多策略组合器。"""
from datetime import datetime

import pytest

from core.strategy_pool.portfolio.composer import MultiStrategyComposer
from core.strategy_pool.schemas.signal_bundle import StrategySignalBundle


def _bundle(strategy_id: str, symbol: str, direction: str, strength: float, confidence: float = 0.7) -> StrategySignalBundle:
    return StrategySignalBundle(
        bundle_id=f"sig-{strategy_id}-{direction}",
        source_strategy_id=strategy_id,
        symbol=symbol,
        timestamp=datetime.utcnow(),
        direction=direction,
        strength=strength,
        confidence=confidence,
    )


class TestMultiStrategyComposer:
    def test_compose_empty(self):
        composer = MultiStrategyComposer()
        result = composer.compose({}, {}, "port-001")
        assert result.portfolio_id == "port-001"
        assert result.composite_direction == "FLAT"

    def test_compose_single_strategy_long(self):
        composer = MultiStrategyComposer()
        bundles = {"trend1": [_bundle("trend1", "AAPL", "LONG", 0.8)]}
        result = composer.compose(bundles, {"trend1": 1.0}, "port-002")
        assert result.composite_direction == "LONG"
        assert result.composite_strength > 0

    def test_compose_two_strategies_same_direction(self):
        composer = MultiStrategyComposer()
        bundles = {
            "trend1": [_bundle("trend1", "AAPL", "LONG", 0.8, 0.9)],
            "mr1": [_bundle("mr1", "AAPL", "LONG", 0.6, 0.8)],
        }
        result = composer.compose(bundles, {"trend1": 0.6, "mr1": 0.4}, "port-003")
        assert result.composite_direction == "LONG"
        assert len(result.proposals) == 2

    def test_compose_conflict_long_vs_short(self):
        composer = MultiStrategyComposer()
        bundles = {
            "trend1": [_bundle("trend1", "AAPL", "LONG", 0.8, 0.9)],
            "reversal1": [_bundle("reversal1", "AAPL", "SHORT", 0.5, 0.7)],
        }
        result = composer.compose(bundles, {"trend1": 0.6, "reversal1": 0.4}, "port-004")
        # trend1 权重更高，所以 LONG 胜出
        assert result.composite_direction == "LONG"

    def test_compose_conflict_reversed_by_weight(self):
        composer = MultiStrategyComposer()
        bundles = {
            "trend1": [_bundle("trend1", "AAPL", "LONG", 0.6, 0.7)],
            "reversal1": [_bundle("reversal1", "AAPL", "SHORT", 0.8, 0.9)],
        }
        result = composer.compose(bundles, {"trend1": 0.3, "reversal1": 0.7}, "port-005")
        # reversal1 权重更高，所以 SHORT 胜出
        assert result.composite_direction == "SHORT"

    def test_proposals_include_portfolio_weight(self):
        composer = MultiStrategyComposer()
        bundles = {"s1": [_bundle("s1", "TSLA", "LONG", 0.7)]}
        result = composer.compose(bundles, {"s1": 0.45}, "port-006")
        assert result.proposals[0].portfolio_weight == 0.45

    def test_flat_when_no_direction(self):
        composer = MultiStrategyComposer()
        bundles = {
            "s1": [_bundle("s1", "AAPL", "LONG", 0.3, 0.5)],
            "s2": [_bundle("s2", "AAPL", "SHORT", 0.3, 0.5)],
        }
        result = composer.compose(bundles, {"s1": 0.5, "s2": 0.5}, "port-007")
        assert result.composite_direction == "FLAT"
