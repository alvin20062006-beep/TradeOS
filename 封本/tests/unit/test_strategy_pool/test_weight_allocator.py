"""单元测试：权重分配器。"""
import pytest

from core.strategy_pool.portfolio.weight_allocator import (
    EqualWeightAllocator,
    IRWeightAllocator,
    InverseVolWeightAllocator,
    RiskParityWeightAllocator,
    make_allocator,
    allocate_portfolio_weights,
)


class TestEqualWeightAllocator:
    def test_equal_weights(self):
        alloc = EqualWeightAllocator()
        weights = alloc.allocate(["s1", "s2", "s3"])
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 1e-9
        assert weights["s1"] == pytest.approx(1 / 3)
        assert weights["s2"] == pytest.approx(1 / 3)
        assert weights["s3"] == pytest.approx(1 / 3)

    def test_empty_list(self):
        alloc = EqualWeightAllocator()
        assert alloc.allocate([]) == {}


class TestInverseVolWeightAllocator:
    def test_inverse_vol(self):
        alloc = InverseVolWeightAllocator()
        metrics = {
            "s1": {"annualized_vol": 0.20},
            "s2": {"annualized_vol": 0.10},
        }
        weights = alloc.allocate(["s1", "s2"], metrics)
        assert len(weights) == 2
        assert abs(sum(weights.values()) - 1.0) < 1e-9
        # s2 波动率更低，权重更高
        assert weights["s2"] > weights["s1"]

    def test_fallback_without_metrics(self):
        alloc = InverseVolWeightAllocator()
        weights = alloc.allocate(["s1", "s2"])
        assert abs(sum(weights.values()) - 1.0) < 1e-9


class TestIRWeightAllocator:
    def test_ir_weights(self):
        alloc = IRWeightAllocator()
        metrics = {
            "s1": {"ir": 0.5},
            "s2": {"ir": 1.5},
        }
        weights = alloc.allocate(["s1", "s2"], metrics)
        assert weights["s2"] > weights["s1"]
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_negative_ir_floored_to_zero(self):
        alloc = IRWeightAllocator()
        metrics = {"s1": {"ir": -0.5}, "s2": {"ir": 0.5}}
        weights = alloc.allocate(["s1", "s2"], metrics)
        assert weights["s1"] >= 0
        assert weights["s2"] > weights["s1"]


class TestRiskParityWeightAllocator:
    def test_fallback_when_no_phase4b(self):
        alloc = RiskParityWeightAllocator()
        # Phase 4B 未安装时降级为逆波动率
        weights = alloc.allocate(["s1", "s2"])
        assert len(weights) == 2
        assert abs(sum(weights.values()) - 1.0) < 1e-9


class TestMakeAllocator:
    def test_factory(self):
        assert isinstance(make_allocator("equal"), EqualWeightAllocator)
        assert isinstance(make_allocator("inverse_vol"), InverseVolWeightAllocator)
        assert isinstance(make_allocator("ir"), IRWeightAllocator)
        assert isinstance(make_allocator("risk_parity"), RiskParityWeightAllocator)

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            make_allocator("unknown")


class TestAllocatePortfolioWeights:
    def test_returns_strategy_weights(self):
        result = allocate_portfolio_weights(["s1", "s2"], "equal")
        assert len(result) == 2
        assert all(hasattr(w, "strategy_id") for w in result)
        assert all(hasattr(w, "weight") for w in result)
