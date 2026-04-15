"""ExecutionAuditor — Phase 3 fills → ExecutionRecord。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from core.audit.schemas.execution_record import ExecutionRecord, FillSnapshot
from core.schemas import ExecutionQuality


class ExecutionAuditor:
    """
    将 Phase 3 fill events + Phase 7 Evaluator 结果转换为 ExecutionRecord。

    职责：
    1. 快照化 Phase 3 Fill[] → FillSnapshot[]
    2. 计算 realized_slippage_bps
    3. 合并 Phase 7 Evaluator pre-trade 预估值
    4. 生成 ExecutionRecord

    使用方式：
        auditor = ExecutionAuditor()
        record = auditor.ingest(fills=[...], evaluator_result={...})
    """

    def ingest(
        self,
        fills: list,
        *,
        plan_id: str,
        symbol: str,
        decision_id: str,
        order_type: str = "MARKET",
        algorithm: str = "",
        evaluator_pre_result: Optional[dict] = None,
        evaluator_post_result: Optional[dict] = None,
        position_plan_id: Optional[str] = None,
        execution_start: Optional[datetime] = None,
        execution_end: Optional[datetime] = None,
    ) -> ExecutionRecord:
        """
        将 Phase 3 fill events 转换为 ExecutionRecord。

        Args:
            fills: Phase 3 fill events list
            plan_id: 关联 PositionPlan ID
            symbol: 标的代码
            decision_id: 关联决策 ID
            order_type: 订单类型
            algorithm: 算法名称
            evaluator_pre_result: Phase 7 Evaluator pre-trade 结果
            evaluator_post_result: Phase 7 Evaluator post-trade 结果
            position_plan_id: PositionPlan ID
            execution_start: 执行开始时间
            execution_end: 执行结束时间
        """
        fill_snapshots = [FillSnapshot.from_fill(f) for f in fills]

        # 计算汇总字段
        total_filled = sum(f.filled_qty for f in fill_snapshots)
        if fill_snapshots:
            avg_price = sum(f.fill_price * f.filled_qty for f in fill_snapshots) / total_filled
        else:
            avg_price = 0.0

        # arrival_price: 从 pre-trade evaluator 或 fill 第一条推断
        arrival_price = 0.0
        if evaluator_pre_result:
            arrival_price = evaluator_pre_result.get("arrival_price", 0.0)
        elif fill_snapshots:
            arrival_price = fill_snapshots[0].fill_price - (
                fill_snapshots[0].slippage_bps / 10000 * fill_snapshots[0].fill_price
            )

        # realized_slippage_bps = (avg_fill - arrival) / arrival × 10000
        realized_slippage = 0.0
        if arrival_price > 0 and avg_price > 0:
            realized_slippage = (avg_price - arrival_price) / arrival_price * 10000

        # 预估值（pre-trade）
        estimated_slippage = 0.0
        estimated_impact = 0.0
        estimated_fill_rate = 1.0
        if evaluator_pre_result:
            estimated_slippage = evaluator_pre_result.get("estimated_slippage_bps", 0.0)
            estimated_impact = evaluator_pre_result.get("estimated_impact_bps", 0.0)
            estimated_fill_rate = evaluator_pre_result.get("estimated_fill_rate", 1.0)

        # 后验评分（post-trade）
        quality_score = 0.0
        quality_rating = ExecutionQuality.FAIR
        realized_impact = 0.0
        if evaluator_post_result:
            quality_score = evaluator_post_result.get("execution_quality_score", 0.0)
            rating_str = evaluator_post_result.get("quality_rating", "FAIR")
            try:
                quality_rating = ExecutionQuality(rating_str)
            except ValueError:
                quality_rating = ExecutionQuality.FAIR
            realized_impact = evaluator_post_result.get("realized_impact_bps", 0.0)

        # 执行时长
        duration = None
        if execution_start and execution_end:
            duration = (execution_end - execution_start).total_seconds()

        return ExecutionRecord(
            audit_id=f"er-{uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            source_phase="Phase 3",
            symbol=symbol,
            decision_id=decision_id,
            plan_id=plan_id,
            order_type=order_type,
            algorithm=algorithm,
            estimated_slippage_bps=estimated_slippage,
            estimated_impact_bps=estimated_impact,
            estimated_fill_rate=estimated_fill_rate,
            fills=fill_snapshots,
            total_requested_qty=getattr(fills[0], "quantity", total_filled) if fills else total_filled,
            total_filled_qty=total_filled,
            fill_rate=min(total_filled / max(getattr(fills[0], "quantity", total_filled) or 1, 1), 1.0),
            avg_execution_price=avg_price,
            arrival_price=arrival_price,
            realized_slippage_bps=realized_slippage,
            realized_impact_bps=realized_impact,
            execution_quality_score=quality_score,
            quality_rating=quality_rating,
            execution_start=execution_start,
            execution_end=execution_end,
            execution_duration_seconds=duration,
            position_plan_id=position_plan_id,
        )
