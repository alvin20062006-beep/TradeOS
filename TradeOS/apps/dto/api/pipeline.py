"""
apps/dto/api/pipeline.py — 全链路编排 API DTO

约束：
- 纯编排层，不重写 Phase 5/6/7/8 内部逻辑
- 只串联现有公开 API/方法
- 不暴露核心内部对象
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── 请求 ────────────────────────────────────────────────────

class PipelineRunFullRequest(BaseModel):
    """
    POST /pipeline/run-full 请求。

    全链路编排：Phase 5 → 6 → 7。
    不重写任何阶段逻辑，只串联已有方法。
    """

    symbol: str = Field(description="标的代码")
    # Phase 5 输入
    direction: Literal["LONG", "SHORT", "FLAT"] = Field(description="信号方向")
    confidence: float = Field(ge=0.0, le=1.0, description="信号置信度")
    strength: float = Field(default=0.5, ge=0.0, le=1.0)
    regime: Literal["trending_up", "trending_down", "ranging", "volatile", "unknown"] = "trending_up"
    # 可选：直接跳过 Phase 5，直接给 ArbitrationDecision 输入
    skip_analysis: bool = Field(
        default=False,
        description="跳过 Phase 5，直接使用下方的 analysis_override 参数",
    )
    analysis_override: Optional[dict] = Field(
        default=None,
        description="Phase 5 原始数据覆盖（跳过分析引擎直接给结果）",
    )
    timestamp: Optional[datetime] = None


# ── 响应 ────────────────────────────────────────────────────

class PipelinePhaseResult(BaseModel):
    """单个阶段的执行结果。"""

    phase: str = Field(description="阶段名：analysis / arbitration / risk")
    ok: bool = True
    duration_ms: float = Field(ge=0.0)
    detail: Optional[dict] = Field(default=None, description="阶段输出摘要")
    error: Optional[str] = Field(default=None)


class PipelineDecisionView(BaseModel):
    """Pipeline 响应中的决策部分（包装 ArbitrationDecision）。"""

    decision_id: str
    symbol: str
    bias: str
    confidence: float
    signal_count: int
    rules_applied: list[str] = Field(default_factory=list)
    timestamp: datetime


class PipelinePlanView(BaseModel):
    """Pipeline 响应中的 PositionPlan 部分。"""

    plan_id: str
    symbol: str
    direction: str
    final_quantity: float
    veto_triggered: bool
    limit_checks: list[dict] = Field(default_factory=list)


class PipelineRunFullResponse(BaseModel):
    """POST /pipeline/run-full 响应。"""

    ok: bool = True
    task_id: str = Field(description="首批：同步处理，固定 immediate")
    status: Literal["done", "partial", "error"] = "done"
    symbol: str
    phases: list[PipelinePhaseResult] = Field(
        default_factory=list,
        description="各阶段执行结果",
    )
    decision: Optional[PipelineDecisionView] = Field(default=None)
    plan: Optional[PipelinePlanView] = Field(default=None)
    error: Optional[str] = Field(default=None)
