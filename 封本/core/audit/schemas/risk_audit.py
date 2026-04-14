"""RiskAudit — Phase 7 风控审计记录。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from core.audit.schemas.audit_record import AuditRecord


class FilterCheckSnapshot(BaseModel):
    """
    Phase 7 FilterResult 的审计快照。

    保留每个过滤器的 mode、passed、adjustment 结果。
    仅保留审计和 feedback 生成所需字段，不强耦合 Phase 7 运行时对象。
    """

    filter_name: str = Field(..., description="过滤器名称")
    mode: str = Field(
        "pass", description="过滤模式：pass（通过）/ cap（调整）/ veto（拒绝）"
    )
    passed: bool = Field(..., description="是否通过过滤")
    raw_qty: float = Field(0.0, ge=0, description="进入过滤器的原始数量")
    adjusted_qty: float = Field(0.0, description="过滤器调整后的数量（可为 0，无 ge 约束）")
    limit_value: Optional[float] = Field(
        None, description="触发限额的具体阈值（如果有）"
    )
    actual_value: Optional[float] = Field(
        None, description="实际值（可为负，如 loss_limit 场景）"
    )
    details: str = Field("", description="人类可读说明")

    @classmethod
    def from_limit_check(cls, lc) -> FilterCheckSnapshot:
        """从 Phase 7 LimitCheck 对象快照化。

        同时处理 dict 和对象两种输入形式。
        """
        if isinstance(lc, dict):
            mode = lc.get("mode", "pass")
            passed = lc.get("passed", True)
            raw_qty = lc.get("raw_qty", 0.0)
            # adjusted_qty 取 adjusted_qty 字段，若无则取 actual_value（容错）
            adjusted_qty = lc.get(
                "adjusted_qty",
                lc.get("actual_value", 0.0),
            )
            limit_value = lc.get("limit_value")
            actual_value = lc.get("actual_value")
            details = lc.get("details", "")
            name = lc.get("limit_name", lc.get("name", "unknown"))
        else:
            mode = getattr(lc, "mode", "pass")
            passed = getattr(lc, "passed", True)
            raw_qty = getattr(lc, "raw_qty", 0.0)
            adjusted_qty = getattr(lc, "adjusted_qty", 0.0)
            limit_value = getattr(lc, "limit_value", None)
            actual_value = getattr(lc, "actual_value", None)
            details = getattr(lc, "details", "")
            name = getattr(lc, "limit_name", "unknown")

        return cls(
            filter_name=name,
            mode=mode,
            passed=passed,
            raw_qty=raw_qty,
            adjusted_qty=adjusted_qty,
            limit_value=limit_value,
            actual_value=actual_value,
            details=details,
        )


class RiskAudit(AuditRecord):
    """
    风控审计记录（Phase 7 → Phase 8）。

    记录风控过滤链的执行结果，用于 filter_pattern feedback 生成。
    """

    source_phase: Literal["Phase 7"] = "Phase 7"

    # ── 关联 ─────────────────────────────────────
    position_plan_id: str = Field(..., description="关联的 PositionPlan ID")
    plan_bias: str = Field(..., description="PositionPlan 的 bias")

    # ── 数量变化链 ──────────────────────────────
    sizing_input_qty: float = Field(
        0.0, ge=0, description="进入风控链前的 sizing 数量"
    )
    input_quantity: float = Field(
        0.0, ge=0, description="进入过滤器链的原始数量"
    )
    final_quantity: float = Field(
        0.0, ge=0, description="过滤器链处理后的最终数量"
    )
    veto_triggered: bool = Field(False)

    # ── 过滤器链快照 ───────────────────────────
    filter_results: List[FilterCheckSnapshot] = Field(
        default_factory=list,
        description="每个过滤器的执行结果快照（FilterCheckSnapshot[]）",
    )

    # ── 汇总 ──────────────────────────────────
    total_adjustments: int = Field(
        0, description="触发调整（mode=cap）的过滤器数量"
    )
    total_vetoes: int = Field(
        0, description="触发拒绝（mode=veto）的过滤器数量"
    )
    veto_filters: List[str] = Field(
        default_factory=list,
        description="触发 veto 的过滤器名称列表",
    )

    # ── 市场状态（供 filter_pattern 分桶用） ─────────
    regime: Optional[str] = Field(None, description="当时的市场状态")
    volatility_regime: Optional[str] = Field(
        None, description="波动率状态：low / normal / high / extreme"
    )
