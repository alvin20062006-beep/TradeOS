"""单元测试：策略生命周期管理。"""
import tempfile

import pytest

from core.strategy_pool.lifecycle.manager import StrategyLifecycleManager
from core.strategy_pool.registry.strategy_registry import StrategyRegistry
from core.strategy_pool.schemas.strategy import StrategySpec, StrategyStatus, StrategyType


def _make_spec(sid: str) -> StrategySpec:
    return StrategySpec(
        strategy_id=sid,
        name=f"Strategy {sid}",
        strategy_type=StrategyType.TREND,
    )


class TestStrategyLifecycleManager:
    def test_activate_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            mgr._registry.register(_make_spec("lc-001"))
            updated = mgr.activate("lc-001")
            assert updated is not None
            assert updated.status == StrategyStatus.ACTIVE
            assert mgr.get_status("lc-001") == StrategyStatus.ACTIVE

    def test_deactivate_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            mgr._registry.register(_make_spec("lc-002"))
            mgr.activate("lc-002")
            mgr.deactivate("lc-002")
            assert mgr.get_status("lc-002") == StrategyStatus.INACTIVE

    def test_deprecate_inactive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            mgr._registry.register(_make_spec("lc-003"))
            mgr.activate("lc-003")
            mgr.deactivate("lc-003")
            mgr.deprecate("lc-003", reason="low performance")
            assert mgr.get_status("lc-003") == StrategyStatus.DEPRECATED

    def test_deprecated_cannot_reactivate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            mgr._registry.register(_make_spec("lc-004"))
            mgr.activate("lc-004")
            mgr.deactivate("lc-004")
            mgr.deprecate("lc-004")
            assert mgr.reactivate("lc-004") is None

    def test_reactivate_inactive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            mgr._registry.register(_make_spec("lc-005"))
            mgr.activate("lc-005")
            mgr.deactivate("lc-005")
            mgr.reactivate("lc-005")
            assert mgr.get_status("lc-005") == StrategyStatus.ACTIVE

    def test_list_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            mgr._registry.register(_make_spec("lc-006"))
            mgr._registry.register(_make_spec("lc-007"))
            mgr.activate("lc-006")
            assert len(mgr.list_candidates()) == 1
            assert len(mgr.list_active()) == 1

    def test_promote_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            mgr._registry.register(_make_spec("lc-008"))
            updated = mgr.promote("lc-008")
            assert updated.status == StrategyStatus.ACTIVE

    def test_activate_unknown_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            assert mgr.activate("nonexistent") is None

    def test_state_machine_full_flow(self):
        """完整状态流：CANDIDATE → ACTIVE → INACTIVE → ACTIVE → DEPRECATED"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = StrategyLifecycleManager(registry=StrategyRegistry(base_path=tmpdir))
            sid = "lc-state-001"
            mgr._registry.register(_make_spec(sid))
            # CANDIDATE
            assert mgr.get_status(sid) == StrategyStatus.CANDIDATE
            # → ACTIVE
            mgr.activate(sid)
            assert mgr.get_status(sid) == StrategyStatus.ACTIVE
            # → INACTIVE
            mgr.deactivate(sid)
            assert mgr.get_status(sid) == StrategyStatus.INACTIVE
            # → ACTIVE（重新激活）
            mgr.reactivate(sid)
            assert mgr.get_status(sid) == StrategyStatus.ACTIVE
            # → DEPRECATED
            mgr.deprecate(sid, reason="end of life")
            assert mgr.get_status(sid) == StrategyStatus.DEPRECATED
