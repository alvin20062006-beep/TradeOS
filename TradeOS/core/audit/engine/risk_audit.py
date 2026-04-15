"""RiskAuditor — Phase 7 PositionPlan → RiskAudit。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from core.audit.schemas.risk_audit import FilterCheckSnapshot, RiskAudit


class RiskAuditor:
    """
    将 Phase 7 PositionPlan 转换为 Phase 8 RiskAudit。

    职责：
    1. 快照化 Phase 7 LimitCheck[] → FilterCheckSnapshot[]
    2. 提取 veto 触发源
    3. 生成 RiskAudit

    使用方式：
        auditor = RiskAuditor()
        risk_audit = auditor.ingest(position_plan)
    """

    def ingest(
        self,
        position_plan,
        *,
        regime: Optional[str] = None,
        volatility_regime: Optional[str] = None,
    ) -> RiskAudit:
        """
        将 Phase 7 PositionPlan 转换为 RiskAudit。

        Args:
            position_plan: Phase 7 RiskEngine.calculate() 输出的 PositionPlan
            regime: 市场状态（供 filter_pattern feedback 分桶）
            volatility_regime: 波动率状态
        """
        filter_results = self._snapshot_filter_results(position_plan)
        veto_filters = [fr.filter_name for fr in filter_results if fr.mode == "veto"]
        total_vetoes = len(veto_filters)
        total_adjustments = sum(1 for fr in filter_results if fr.mode == "cap")

        return RiskAudit(
            audit_id=f"ra-{uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            source_phase="Phase 7",
            symbol=getattr(position_plan, "symbol", ""),
            decision_id=getattr(position_plan, "decision_id", ""),
            position_plan_id=getattr(position_plan, "plan_id", ""),
            plan_bias=getattr(position_plan, "bias", ""),
            sizing_input_qty=getattr(position_plan, "base_quantity", 0.0),
            input_quantity=getattr(position_plan, "base_quantity", 0.0),
            final_quantity=getattr(position_plan, "final_quantity", 0.0),
            veto_triggered=getattr(position_plan, "veto_triggered", False),
            filter_results=filter_results,
            total_adjustments=total_adjustments,
            total_vetoes=total_vetoes,
            veto_filters=veto_filters,
            regime=regime,
            volatility_regime=volatility_regime,
        )

    def _snapshot_filter_results(self, position_plan) -> List[FilterCheckSnapshot]:
        """快照化 LimitCheck[] → FilterCheckSnapshot[]（统一使用 from_limit_check）。"""
        raw_checks = getattr(position_plan, "limit_checks", []) or []
        return [FilterCheckSnapshot.from_limit_check(lc) for lc in raw_checks]
