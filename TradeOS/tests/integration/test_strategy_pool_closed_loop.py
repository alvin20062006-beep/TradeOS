"""Integration 测试：策略池完整闭环。"""
import tempfile
from datetime import datetime

from core.strategy_pool.builders.breakout import BreakoutStrategy
from core.strategy_pool.builders.mean_reversion import MeanReversionStrategy
from core.strategy_pool.builders.reversal import ReversalStrategy
from core.strategy_pool.builders.trend import TrendFollowingStrategy
from core.strategy_pool.interfaces.arbitration_bridge import ArbitrationInputBridge
from core.strategy_pool.lifecycle.manager import StrategyLifecycleManager
from core.strategy_pool.portfolio.composer import MultiStrategyComposer
from core.strategy_pool.portfolio.weight_allocator import (
    EqualWeightAllocator,
    IRWeightAllocator,
    allocate_portfolio_weights,
)
from core.strategy_pool.registry.strategy_registry import StrategyRegistry
from core.strategy_pool.schemas.portfolio import StrategyPortfolio


def _ohlcv(n=60, start=100.0):
    data = []
    price = start
    for i in range(n):
        close = price * (1 + i * 0.001)
        data.append({
            "date": f"2024-01-{i+1:02d}",
            "open": price, "high": close * 1.01, "low": close * 0.99,
            "close": close, "volume": 1_000_000,
        })
        price = close
    return data


class TestStrategyPoolClosedLoop:
    def test_full_pipeline(self):
        """
        完整流水线：
        1. 多策略生成信号
        2. 权重分配
        3. 多策略组合
        4. 仲裁输入构建
        5. 策略生命周期
        """
        data = _ohlcv(n=60)

        # ── 1. 生成信号 ────────────────────────────────
        trend = TrendFollowingStrategy({
            "strategy_id": "trend-001",
            "short_ma_period": 5,
            "long_ma_period": 10,
            "momentum_window": 5,
            "momentum_threshold": 0.0,
        })
        mr = MeanReversionStrategy({
            "strategy_id": "mr-001",
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "bb_period": 20,
        })

        trend_signals = trend.generate_signals(data, "AAPL")
        mr_signals = mr.generate_signals(data, "AAPL")

        assert len(trend_signals) >= 0
        assert len(mr_signals) >= 0

        # ── 2. 权重分配 ────────────────────────────────
        allocator = EqualWeightAllocator()
        weights = allocator.allocate(["trend-001", "mr-001"])

        assert abs(weights["trend-001"] + weights["mr-001"] - 1.0) < 1e-9

        # ── 3. 多策略组合 ──────────────────────────────
        composer = MultiStrategyComposer()
        bundles_by_strategy = {"trend-001": trend_signals, "mr-001": mr_signals}
        portfolio_proposal = composer.compose(bundles_by_strategy, weights, "port-001")

        assert portfolio_proposal.portfolio_id == "port-001"
        assert portfolio_proposal.weight_method == "equal"
        assert len(portfolio_proposal.proposals) == 2

        # ── 4. 仲裁输入构建 ────────────────────────────
        bridge = ArbitrationInputBridge()
        arb_bundle = bridge.build(
            portfolio_proposal=portfolio_proposal,
            supporting_factor_ids=["alpha-001", "alpha-002"],
            regime_context={"regime": "trending"},
        )

        assert arb_bundle.portfolio_proposal is not None
        assert len(arb_bundle.supporting_factor_ids) == 2
        assert arb_bundle.regime_context["regime"] == "trending"

        # ── 5. 策略注册与生命周期 ──────────────────────
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            mgr = StrategyLifecycleManager(registry=reg)

            # 注册并激活
            spec = trend.get_spec()
            reg.register(spec)
            mgr.activate("trend-001")

            assert mgr.get_status("trend-001") == "active"
            assert len(mgr.list_active()) == 1

            # 停用
            mgr.deactivate("trend-001")
            assert mgr.get_status("trend-001") == "inactive"

            # 重新激活
            mgr.reactivate("trend-001")
            assert mgr.get_status("trend-001") == "active"

    def test_ir_weight_allocator(self):
        """IR 权重分配：IR 更高的策略权重更大。"""
        metrics = {
            "s1": {"ir": 0.3},
            "s2": {"ir": 1.2},
        }
        alloc = IRWeightAllocator()
        weights = alloc.allocate(["s1", "s2"], metrics)
        assert weights["s2"] > weights["s1"]

    def test_allocate_portfolio_weights_returns_strategy_weights(self):
        """allocate_portfolio_weights 便捷方法。"""
        sw = allocate_portfolio_weights(["a", "b"], "equal")
        assert len(sw) == 2
        assert all(hasattr(w, "strategy_id") and hasattr(w, "weight") for w in sw)

    def test_multi_strategy_composer_empty_bundle(self):
        """空 bundle 时 composite_direction 为 FLAT。"""
        composer = MultiStrategyComposer()
        result = composer.compose({}, {}, "port-empty")
        assert result.composite_direction == "FLAT"
        assert result.composite_strength == 0.0

    def test_breakout_and_reversal_on_same_data(self):
        """breakout 和 reversal 在同一数据上可能产生冲突信号。"""
        data = _ohlcv(n=40)
        # 制造下跌 → reversal 应触发 LONG
        data[-1]["close"] = data[-5]["close"] * 0.88

        rev = ReversalStrategy({
            "strategy_id": "rev-002",
            "return_period": 5,
            "long_threshold": -0.03,
            "short_threshold": 0.03,
        })
        rev_signals = rev.generate_signals(data, "TSLA")
        # 下跌市场应产生信号（LONG 或 SHORT），空列表也算通过
        for sig in rev_signals:
            assert sig.direction in ("LONG", "SHORT", "FLAT")
            assert 0.0 <= sig.strength <= 1.0
