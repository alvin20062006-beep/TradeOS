"""
Phase 7 Risk Layer Schemas
=========================

只新增3个 schema，与 core.schemas 风格一致。
不复用平行 dataclass 体系。

- PositionPlan      : 仓位计算中间结果（仲裁决策 → 最终仓位）
- ExecutionPlan     : 执行计划中间对象（仓位计划 → 执行指令）
- ExecutionQualityReport : 执行质量报告（pre-trade 预估 / post-trade 实际）
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from core.schemas import Direction, ExecutionQuality, OrderType


# ─────────────────────────────────────────────────────────────
# ExecutionQualityReport
# ─────────────────────────────────────────────────────────────

class ExecutionQualityReport(BaseModel):
    """
    执行质量报告。

    通过 is_pre_trade 区分预估与实际：
    - is_pre_trade=True  : ExecutionPlanner 生成，预估字段有值，realized_* 字段为空
    - is_pre_trade=False : Phase 3 执行完成后填充，realized_* 字段有值
    """
    evaluation_id: str = Field(..., description="唯一评估 ID")
    plan_id: str = Field(..., description="关联 ExecutionPlan ID")

    is_pre_trade: bool = Field(
        ..., description="True=预估报告，False=事后评估报告"
    )

    # ── 基础标识 ─────────────────────────────────────
    symbol: str
    direction: Direction
    timestamp: datetime

    # ── Pre-trade 预估字段 ───────────────────────────
    estimated_slippage_bps: Optional[float] = Field(
        None, ge=0, description="预估滑点（bps）"
    )
    estimated_impact_bps: Optional[float] = Field(
        None, ge=0, description="预估市场冲击（bps）"
    )
    estimated_participation_rate: Optional[float] = Field(
        None, ge=0, le=1, description="预估参与率"
    )
    participation_risk: Optional[str] = Field(
        None, description="参与率风险：low / medium / high"
    )

    # ── Post-trade 实际字段 ──────────────────────────
    # 实际执行数据（来自 Phase 3 OrderRecord / FillRecord）
    actual_filled_quantity: Optional[float] = Field(None, ge=0)
    avg_fill_price: Optional[float] = Field(None, gt=0)
    arrival_price: Optional[float] = Field(None, gt=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = Field(None, ge=0)

    # 实际质量指标
    realized_slippage_bps: Optional[float] = Field(None)
    realized_impact_bps: Optional[float] = Field(None)
    implementation_shortfall_bps: Optional[float] = Field(None)
    fill_rate: Optional[float] = Field(None, ge=0, le=1)
    actual_participation_rate: Optional[float] = Field(None, ge=0, le=1)

    # ── 评分（pre-trade 为预估，post-trade 为实际） ──
    execution_score: float = Field(0.0, ge=0, le=1)
    quality_rating: ExecutionQuality = Field(
        ExecutionQuality.GOOD,
        description="EXCELLENT/GOOD/FAIR/POOR/FAILED",
    )

    # 评分因子
    slippage_score: float = Field(0.0, ge=0, le=1)
    impact_score: float = Field(0.0, ge=0, le=1)
    fill_rate_score: float = Field(0.0, ge=0, le=1)
    timing_score: float = Field(0.0, ge=0, le=1)

    # ── vs 计划偏离 ─────────────────────────────────
    vs_plan_slippage_bps: Optional[float] = Field(
        None, description="实际 vs 预估滑点偏离（bps）"
    )
    vs_plan_impact_bps: Optional[float] = Field(
        None, description="实际 vs 预估冲击偏离（bps）"
    )

    metadata: dict = Field(default_factory=dict)

    @property
    def has_realized_data(self) -> bool:
        """是否有事后实际数据。"""
        return self.realized_slippage_bps is not None


# ─────────────────────────────────────────────────────────────
# ExecutionPlan
# ─────────────────────────────────────────────────────────────

class ExecutionSlice(BaseModel):
    """单个执行分片（TWAP/VWAP/POV/Adaptive）。"""
    slice_id: int = Field(..., ge=0)
    quantity: float = Field(..., gt=0)
    start_time: datetime
    end_time: datetime
    target_price: Optional[float] = Field(None, gt=0)
    order_type: OrderType = Field(OrderType.LIMIT)
    # 分片参与率（POV/Adaptive 用）
    slice_participation_rate: Optional[float] = Field(None, ge=0, le=1)


class ExecutionPlan(BaseModel):
    """
    执行计划。

    包含算法选择、分片计划、预估冲击。
    由 ExecutionPlanner 生成，Phase 3 执行底盘消费。

    PositionPlan.final_quantity → ExecutionPlan.target_quantity
    """
    plan_id: str = Field(..., description="唯一计划 ID")
    position_plan_id: str = Field(..., description="关联 PositionPlan ID")
    decision_id: str = Field(..., description="关联 ArbitrationDecision ID")

    timestamp: datetime
    symbol: str
    direction: Direction

    # ── 目标数量 ──────────────────────────────────
    target_quantity: float = Field(..., ge=0, description="目标数量（可为零，用于 no_trade plan）")
    notional_value: float = Field(..., ge=0, description="名义价值（qty × price）")

    # ── 算法选择 ──────────────────────────────────
    algorithm: OrderType = Field(
        OrderType.MARKET,
        description="MARKET/LIMIT/TWAP/VWAP/POV/ICEBERG/ADAPTIVE",
    )
    algorithm_params: dict = Field(
        default_factory=dict,
        description="算法具体参数（参与率/切片数/限价等）",
    )
    urgency: str = Field(
        "medium", description="low / medium / high"
    )

    # ── 价格约束 ──────────────────────────────────
    limit_price: Optional[float] = Field(None, gt=0)
    worst_price: Optional[float] = Field(None, gt=0)
    arrival_price: Optional[float] = Field(None, ge=0)  # 可为零（plan 时未知）

    # ── 时间约束 ──────────────────────────────────
    time_limit_seconds: int = Field(900, ge=60, description="最大执行时间（秒）")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # ── 参与率 ────────────────────────────────────
    max_participation_rate: float = Field(0.10, ge=0, le=1)
    target_participation_rate: float = Field(0.05, ge=0, le=1)

    # ── 平方根冲击预估 ────────────────────────────
    estimated_impact_bps: float = Field(0.0, ge=0, description="预估市场冲击（bps）")
    estimated_slippage_bps: float = Field(0.0, ge=0, description="预估滑点（bps）")
    participation_risk: str = Field(
        "low", description="low / medium / high"
    )

    # ── 分片（TWAP/VWAP/POV/Adaptive） ──────────
    slices: List[ExecutionSlice] = Field(
        default_factory=list,
        description="分片列表（MARKET/LIMIT 无分片）",
    )

    # ── 计划质量评分 ──────────────────────────────
    execution_score: float = Field(0.0, ge=0, le=1)
    score_factors: dict = Field(default_factory=dict)

    # ── Pre-trade 质量预估报告 ───────────────────
    pre_trade_report: Optional[ExecutionQualityReport] = Field(
        None,
        description="由 Evaluator.estimate() 生成的预估值",
    )

    metadata: dict = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# PositionPlan
# ─────────────────────────────────────────────────────────────

class RiskAdjustment(BaseModel):
    """单次风控调整记录。"""
    filter_name: str = Field(..., description="触发调整的过滤器名称")
    adjustment_type: str = Field(
        ..., description="reduced / zeroed / capped / vetoed"
    )
    original_quantity: float = Field(..., ge=0)
    adjusted_quantity: float = Field(..., ge=0)
    reason: str


class LimitCheck(BaseModel):
    """
    单条风控限额检查结果。

    Attributes
    ----------
    limit_name : str
        过滤器名称（对应 RiskFilter.name）
    limit_value : float
        限额阈值
    raw_qty : float
        过滤器接收到的原始数量（未经本轮 filter 修改）
    actual_value : float
        限额检查使用的实际值（经过前序 filters 调整后的当前数量）
    passed : bool
        是否通过
    mode : str
        过滤器行为："pass" / "cap" / "veto"
    details : str
        人类可读说明
    """
    limit_name: str = Field(..., description="限额名称：max_position_pct / ...")
    limit_value: float = Field(..., description="限额阈值")
    raw_qty: float = Field(..., description="原始数量（进入 filter 链之前）")
    actual_value: float = Field(..., description="检查时数量（经前序 filters 调整后）")
    passed: bool = Field(..., description="是否通过")
    mode: str = Field("pass", description="'pass' | 'cap' | 'veto'")
    details: str = Field("")


class PositionPlan(BaseModel):
    """
    仓位计划。

    输入：ArbitrationDecision（Phase 6）
    输出：ExecutionIntent（Phase 3）可映射的仓位数据

    核心链路：
      ArbitrationDecision → RiskEngine → PositionPlan → ExecutionPlanner → ExecutionPlan
    """
    plan_id: str = Field(..., description="唯一仓位计划 ID（UUID）")
    decision_id: str = Field(..., description="关联 ArbitrationDecision ID")
    timestamp: datetime
    symbol: str

    # ── 来自仲裁层 ────────────────────────────────
    bias: str = Field(
        ...,
        description="仲裁层 bias：no_trade/long_bias/short_bias/hold_bias/reduce_risk/exit_bias",
    )
    arbitration_confidence: float = Field(0.0, ge=0, le=1)

    # ── 方向 ────────────────────────────────────
    direction: Direction = Field(..., description="LONG / SHORT")

    # ── 仓位计算结果 ─────────────────────────────
    sizing_method: str = Field(
        "",
        description="sizing 算法名称：volatility_targeting / kelly / conviction_weighted / fixed_fraction / drawdown_adjusted / regime_based",
    )
    base_quantity: float = Field(
        0.0, ge=0, description="sizing 公式计算的理论数量"
    )
    final_quantity: float = Field(
        0.0, ge=0, description="最终确认数量（经风控过滤后，>0 时可执行）"
    )
    notional_value: float = Field(
        0.0, ge=0, description="名义价值（final_quantity × current_price）"
    )
    current_price: float = Field(0.0, gt=0, description="计算时标的现价")

    # ── 风控记录 ─────────────────────────────────
    risk_adjustments: List[RiskAdjustment] = Field(
        default_factory=list, description="风控调整链"
    )
    limit_checks: List[LimitCheck] = Field(
        default_factory=list, description="限额检查结果"
    )
    veto_triggered: bool = Field(
        False, description="是否触发 veto（任意风控过滤器强制清零）"
    )
    veto_reasons: List[str] = Field(
        default_factory=list, description="veto 原因列表"
    )
    sizing_rationale: str = Field(
        "", description="人类可读 sizing 理由"
    )

    # ── 执行动作（内部语义，解耦 direction） ─────
    # direction: 目标剩余暴露方向（LONG/SHORT/FLAT）
    # exec_action: 执行动作（BUY/SELL/FLAT）
    #             与 direction 解耦，专供 ExecutionLayer 决定下单方向
    #   reduce LONG 200: direction=LONG, exec_action=SELL, final_qty=200
    #   open LONG 750:   direction=LONG, exec_action=BUY,  final_qty=750
    #   exit LONG 200:   direction=SHORT,exec_action=SELL, final_qty=200
    #   exit SHORT 150:  direction=LONG, exec_action=BUY,  final_qty=150
    exec_action: Optional[str] = Field(
        None,
        description="执行动作：BUY（开多/平空）/ SELL（开空/平多）/ FLAT（无动作）",
    )

    # ── 执行计划（由 ExecutionPlanner 填充） ─────
    execution_plan: Optional[ExecutionPlan] = Field(
        None, description="关联执行计划"
    )

    # ── 辅助 ─────────────────────────────────────
    portfolio_snapshot_equity: float = Field(
        0.0, ge=0, description="计算时的组合权益快照"
    )

    @property
    def is_actionable(self) -> bool:
        """是否有可执行仓位。"""
        return self.final_quantity > 0 and not self.veto_triggered

    @property
    def is_reducing(self) -> bool:
        """是否正在减仓（exit_bias / reduce_risk）。"""
        return self.bias in ("exit_bias", "reduce_risk")
