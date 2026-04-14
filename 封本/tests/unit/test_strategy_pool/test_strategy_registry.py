"""单元测试：策略注册表。"""
import tempfile

import pytest

from core.strategy_pool.registry.strategy_registry import StrategyRegistry
from core.strategy_pool.schemas.strategy import StrategySpec, StrategyStatus, StrategyType


def make_spec(strategy_id: str, status: StrategyStatus = StrategyStatus.CANDIDATE) -> StrategySpec:
    return StrategySpec(
        strategy_id=strategy_id,
        name=f"Strategy {strategy_id}",
        strategy_type=StrategyType.TREND,
        status=status,
    )


class TestStrategyRegistry:
    def test_register_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            spec = make_spec("s-register-001")
            reg.register(spec)
            fetched = reg.get("s-register-001")
            assert fetched is not None
            assert fetched.strategy_id == "s-register-001"
            assert fetched.status == StrategyStatus.CANDIDATE

    def test_register_duplicate_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            reg.register(make_spec("s-dup-001"))
            with pytest.raises(ValueError, match="already exists"):
                reg.register(make_spec("s-dup-001"))

    def test_activate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            reg.register(make_spec("s-act-001"))
            updated = reg.activate("s-act-001")
            assert updated is not None
            assert updated.status == StrategyStatus.ACTIVE
            assert updated.activated_at is not None
            # 原 CANDIDATE 记录仍存在，但 get() 取最新 ACTIVE 版本
            assert reg.get("s-act-001").status == StrategyStatus.ACTIVE

    def test_activate_unknown_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            assert reg.activate("nonexistent") is None

    def test_deactivate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            reg.register(make_spec("s-deact-001"))
            reg.activate("s-deact-001")
            updated = reg.deactivate("s-deact-001")
            assert updated.status == StrategyStatus.INACTIVE
            assert reg.get("s-deact-001").status == StrategyStatus.INACTIVE

    def test_deprecate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            reg.register(make_spec("s-dep-001"))
            reg.deactivate("s-dep-001")
            updated = reg.deprecate("s-dep-001", reason="low ir")
            assert updated.status == StrategyStatus.DEPRECATED
            assert updated.deprecation_reason == "low ir"

    def test_reactivate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            reg.register(make_spec("s-react-001"))
            reg.activate("s-react-001")
            reg.deactivate("s-react-001")
            updated = reg.reactivate("s-react-001")
            assert updated.status == StrategyStatus.ACTIVE

    def test_deprecated_cannot_activate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            reg.register(make_spec("s-noact-001"))
            reg.deprecate("s-noact-001", reason="bad")
            assert reg.activate("s-noact-001") is None

    def test_list_by_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = StrategyRegistry(base_path=tmpdir)
            reg.register(make_spec("s-list-001"))
            reg.register(make_spec("s-list-002"))
            reg.register(make_spec("s-list-003"))
            reg.activate("s-list-001")
            reg.activate("s-list-002")
            assert len(reg.list_by_status(StrategyStatus.ACTIVE)) == 2
            assert len(reg.list_by_status(StrategyStatus.CANDIDATE)) == 1
            assert len(reg.list_by_status(StrategyStatus.DEPRECATED)) == 0
