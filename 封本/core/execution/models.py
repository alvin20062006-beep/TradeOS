"""
Execution Models - 本项目执行层数据模型

定义所有执行相关对象：
- ExecutionIntent: 执行意图（决策层 → 执行层）
- ExecutionReport: 执行报告（执行层 → 调用方）
- PositionState: 仓位状态
- OrderRecord: 订单记录
- FillRecord: 成交记录
- ExecutionRiskFlag: 风险标记
- StatusTransition: 状态转换记录
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any

from pydantic import BaseModel, Field

from ai_trading_tool.core.execution.enums import (
    Side,
    OrderType,
    TimeInForce,
    Urgency,
    ExecutionStatus,
    LiquiditySide,
    RiskFlagType,
    RiskSeverity,
    EngineStatus,
)


# ─────────────────────────────────────────────────────────────
# 状态转换记录
# ─────────────────────────────────────────────────────────────

class StatusTransition(BaseModel):
    """状态转换记录
    
    记录订单状态变化历史，用于审计追踪。
    """
    from_status: ExecutionStatus
    to_status: ExecutionStatus
    timestamp: datetime = Field(default_factory=datetime.now)
    reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# 执行风险标记
# ─────────────────────────────────────────────────────────────

class ExecutionRiskFlag(BaseModel):
    """执行风险标记
    
    附加在 ExecutionIntent 上的风控标记，由风控层生成。
    """
    flag_type: RiskFlagType
    severity: RiskSeverity
    
    # 参数
    threshold_value: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None
    
    # 说明
    description: Optional[str] = None
    triggered_at: datetime = Field(default_factory=datetime.now)
    
    # 来源
    source: Optional[str] = None  # 风控模块名称


# ─────────────────────────────────────────────────────────────
# 执行意图
# ─────────────────────────────────────────────────────────────

class ExecutionIntent(BaseModel):
    """执行意图
    
    决策层向执行层发出的交易指令。
    这是本项目内部对象，不直接依赖 NautilusTrader。
    """
    
    # 标识
    intent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str                    # 来源策略ID
    decision_id: Optional[str] = None   # 关联决策ID（来自仲裁层）
    
    # 标的
    symbol: str                         # 交易标的，如 "AAPL"
    venue: Optional[str] = None         # 交易所/venue，如 "NASDAQ", "BINANCE"
    
    # 方向与数量
    side: Side                          # BUY / SELL
    order_type: OrderType               # MARKET / LIMIT / STOP / etc.
    quantity: Decimal                   # 数量（正数）
    
    # 价格参数
    price: Optional[Decimal] = None     # 限价（LIMIT/STOP_LIMIT）
    stop_price: Optional[Decimal] = None  # 止损触发价
    
    # 时间属性
    time_in_force: TimeInForce = TimeInForce.DAY
    expire_at: Optional[datetime] = None  # 过期时间（GTD）
    
    # 执行控制（预留，Phase 7 平方根执行算法使用）
    execution_algo: Optional[str] = None   # 执行算法名称：twap, vwap, pov, etc.
    urgency: Urgency = Urgency.NORMAL      # 紧急程度
    max_slippage_bps: Optional[int] = None  # 最大滑点（基点）
    participation_rate_limit: Optional[Decimal] = None  # 参与率上限
    
    # 风控标记
    risk_flags: list[ExecutionRiskFlag] = Field(default_factory=list)
    
    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    
    def has_blocking_risk(self) -> bool:
        """检查是否有阻塞性风险标记"""
        return any(f.severity == RiskSeverity.BLOCK for f in self.risk_flags)


# ─────────────────────────────────────────────────────────────
# 执行报告
# ─────────────────────────────────────────────────────────────

class ExecutionReport(BaseModel):
    """执行报告
    
    订单执行状态反馈，由执行层生成并返回调用方。
    """
    
    # 标识
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent_id: str                      # 关联的意图ID
    order_id: Optional[str] = None      # 交易所/Nautilus订单ID
    
    # 状态
    status: ExecutionStatus             # PENDING / SUBMITTED / ... / FILLED
    
    # 时间戳
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    last_update_at: datetime = Field(default_factory=datetime.now)
    
    # 成交信息
    filled_qty: Decimal = Decimal("0")
    remaining_qty: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    total_fees: Decimal = Decimal("0")
    
    # 执行质量
    slippage_estimate_bps: Optional[int] = None  # 滑点估算（基点）
    venue_latency_ms: Optional[int] = None       # 交易所延迟（毫秒）
    
    # 来源信息
    venue: Optional[str] = None
    raw_reference: Optional[str] = None  # Nautilus原始引用
    
    # 拒绝信息
    reject_reason: Optional[str] = None
    reject_code: Optional[str] = None
    
    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self.status in (
            ExecutionStatus.FILLED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.EXPIRED,
        )
    
    @property
    def is_complete(self) -> bool:
        """是否完全成交"""
        return self.status == ExecutionStatus.FILLED


# ─────────────────────────────────────────────────────────────
# 成交记录
# ─────────────────────────────────────────────────────────────

class FillRecord(BaseModel):
    """成交记录
    
    单笔成交详情，用于审计和结算。
    """
    
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str                       # 关联订单ID
    intent_id: str                      # 关联意图ID
    
    # 成交内容
    symbol: str
    side: Side
    filled_qty: Decimal
    fill_price: Decimal
    fees: Decimal = Decimal("0")
    
    # 执行信息
    venue: Optional[str] = None
    trade_id: Optional[str] = None      # 交易所成交ID
    liquidity_side: Optional[LiquiditySide] = None  # MAKER / TAKER
    
    # 时间
    filled_at: datetime
    
    # 原始引用
    raw_reference: Optional[str] = None  # Nautilus原始引用
    
    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# 订单记录
# ─────────────────────────────────────────────────────────────

class OrderRecord(BaseModel):
    """订单记录
    
    完整订单生命周期记录，用于审计。
    """
    
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent_id: str
    order_id: str                       # 交易所/Nautilus订单ID
    
    # 订单内容（创建时快照）
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal]
    stop_price: Optional[Decimal]
    time_in_force: TimeInForce
    
    # 状态追踪
    status_history: list[StatusTransition] = Field(default_factory=list)
    current_status: ExecutionStatus = ExecutionStatus.PENDING
    
    # 关联
    fills: list[str] = Field(default_factory=list)  # FillRecord IDs
    
    # 时间
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def add_transition(
        self,
        to_status: ExecutionStatus,
        reason: Optional[str] = None,
    ) -> StatusTransition:
        """添加状态转换"""
        transition = StatusTransition(
            from_status=self.current_status,
            to_status=to_status,
            reason=reason,
        )
        self.status_history.append(transition)
        self.current_status = to_status
        self.updated_at = datetime.now()
        return transition


# ─────────────────────────────────────────────────────────────
# 仓位状态
# ─────────────────────────────────────────────────────────────

class PositionState(BaseModel):
    """仓位状态
    
    聚合后的持仓信息，由 PortfolioAdapter 生成。
    """
    
    # 标识
    position_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    venue: Optional[str] = None
    
    # 数量与成本
    net_qty: Decimal = Decimal("0")     # 净持仓（正=多，负=空）
    avg_cost: Decimal = Decimal("0")    # 平均成本
    total_traded_qty: Decimal = Decimal("0")
    
    # 盈亏
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    
    # 风险指标
    exposure: Decimal = Decimal("0")    # 敞口（市值）
    margin_used: Optional[Decimal] = None
    
    # 时间
    opened_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 来源
    source_orders: list[str] = Field(default_factory=list)  # 来源订单IDs
    source_fills: list[str] = Field(default_factory=list)   # 来源成交IDs
    
    @property
    def is_long(self) -> bool:
        """是否多头"""
        return self.net_qty > 0
    
    @property
    def is_short(self) -> bool:
        """是否空头"""
        return self.net_qty < 0
    
    @property
    def is_flat(self) -> bool:
        """是否空仓"""
        return self.net_qty == 0


# ─────────────────────────────────────────────────────────────
# 订单快照
# ─────────────────────────────────────────────────────────────

class OrderSnapshot(BaseModel):
    """订单快照
    
    订单当前状态的轻量级视图。
    """
    
    order_id: str
    symbol: str
    venue: Optional[str] = None
    side: Side
    order_type: OrderType
    status: str                         # ExecutionStatus 值
    
    # 数量
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    remaining_quantity: Optional[Decimal] = None
    
    # 价格
    price: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    
    # 时间
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────
# 运行时报告
# ─────────────────────────────────────────────────────────────

class RuntimeReport(BaseModel):
    """运行时报告
    
    ExecutionRuntime 的健康状态报告。
    """
    
    status: str                         # EngineStatus 值
    mode: str                           # ExecutionMode 值
    started_at: Optional[str] = None    # ISO格式时间戳
    stopped_at: Optional[str] = None    # ISO格式时间戳
    
    # Adapter 状态
    adapters: dict[str, str] = Field(default_factory=dict)  # venue -> status
    
    # 统计
    total_orders: int = 0
    total_fills: int = 0
    
    # 错误信息
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None
