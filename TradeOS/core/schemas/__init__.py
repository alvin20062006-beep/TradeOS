"""
Global Schema Definitions for AI Trading Tool

All market data, signals, decisions, and execution records
MUST use these schema definitions. No ad-hoc fields allowed.

Phase 1 Schema List:
- MarketBar, MarketTick, OrderBookSnapshot, TradePrint
- FundamentalsSnapshot, MacroEvent, NewsEvent, SentimentEvent
- EngineSignal, ArbitrationDecision, RiskEvent
- ExecutionIntent, OrderRecord, FillRecord, AuditRecord
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────

class TimeFrame(str, Enum):
    """Market timeframes."""
    S1 = "1s"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN = "1M"


class Side(str, Enum):
    """Trade side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TWAP = "twap"
    VWAP = "vwap"
    POV = "pov"
    ICEBERG = "iceberg"
    ADAPTIVE = "adaptive"


class Direction(str, Enum):
    """Trading direction."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class Regime(str, Enum):
    """Market regime."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExecutionQuality(str, Enum):
    """Execution quality rating."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    FAILED = "failed"


class RiskEventType(str, Enum):
    """Risk event types."""
    MAX_POSITION_BREACH = "max_position_breach"
    MAX_LOSS_BREACH = "max_loss_breach"
    DRAWDOWN_BREACH = "drawdown_breach"
    MARGIN_CALL = "margin_call"
    LIQUIDATION_RISK = "liquidation_risk"
    CONCENTRATION_RISK = "concentration_risk"
    CORRELATION_RISK = "correlation_risk"
    REGIME_CHANGE = "regime_change"


class EventSource(str, Enum):
    """Event source origin."""
    EXCHANGE = "exchange"
    BROKER = "broker"
    ENGINE = "engine"
    RISK = "risk"
    USER = "user"
    SYSTEM = "system"


# ─────────────────────────────────────────────────────────────
# MARKET DATA SCHEMAS
# ─────────────────────────────────────────────────────────────

class MarketBar(BaseModel):
    """
    OHLCV Bar data.
    
    Core market data unit for technical analysis.
    """
    symbol: str = Field(..., description="Trading symbol, e.g., 'AAPL'")
    timeframe: TimeFrame = Field(..., description="Bar timeframe")
    timestamp: datetime = Field(..., description="Bar open time (UTC)")
    
    # OHLCV
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price")
    low: float = Field(..., gt=0, description="Lowest price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: float = Field(..., ge=0, description="Volume")
    
    # Optional
    quote_volume: Optional[float] = Field(None, ge=0, description="Quote volume (USD)")
    trades: Optional[int] = Field(None, ge=0, description="Number of trades")
    vwap: Optional[float] = Field(None, gt=0, description="Volume weighted average price")
    
    # Metadata
    source: Optional[str] = Field(None, description="Data source")
    
    @field_validator("high")
    @classmethod
    def high_ge_open(cls, v: float, info) -> float:
        if "open" in info.data and v < info.data["open"]:
            raise ValueError(f"high ({v}) must be >= open ({info.data['open']})")
        return v
    
    @field_validator("close")
    @classmethod
    def close_ge_low(cls, v: float, info) -> float:
        if "low" in info.data and v < info.data["low"]:
            raise ValueError(f"close ({v}) must be >= low ({info.data['low']})")
        return v


class MarketTick(BaseModel):
    """
    Individual market tick.
    
    Lowest granularity market data.
    """
    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Tick timestamp (UTC)")
    price: float = Field(..., gt=0, description="Last trade price")
    size: float = Field(..., ge=0, description="Last trade size")
    side: Optional[Side] = Field(None, description="Trade side (if available)")
    
    # Bid/Ask at time of tick
    bid: Optional[float] = Field(None, gt=0)
    ask: Optional[float] = Field(None, gt=0)
    bid_size: Optional[float] = Field(None, ge=0)
    ask_size: Optional[float] = Field(None, ge=0)


class OrderBookSnapshot(BaseModel):
    """
    Full order book snapshot.
    
    For order flow and liquidity analysis.
    """
    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Snapshot timestamp (UTC)")
    
    # Levels: list of (price, size)
    bids: list[tuple[float, float]] = Field(
        ..., description="Bid levels [(price, size), ...], sorted descending"
    )
    asks: list[tuple[float, float]] = Field(
        ..., description="Ask levels [(price, size), ...], sorted ascending"
    )
    
    # Derived
    bid_depth: float = Field(0, ge=0, description="Total bid volume")
    ask_depth: float = Field(0, ge=0, description="Total ask volume")
    spread: float = Field(0, ge=0, description="Ask-Bid spread")
    mid_price: float = Field(0, gt=0, description="Mid price")
    
    # Imbalance metrics
    imbalance: float = Field(0, description="Order book imbalance (-1 to 1)")
    
    @field_validator("bids", "asks", mode="before")
    @classmethod
    def validate_levels(cls, v):
        if not v:
            return []
        return v


class TradePrint(BaseModel):
    """
    Single trade print from exchange.
    
    For aggressive buy/sell analysis and CVD tracking.
    """
    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Trade timestamp (UTC)")
    price: float = Field(..., gt=0, description="Trade price")
    size: float = Field(..., gt=0, description="Trade size")
    side: Side = Field(..., description="Aggressive side (initiator)")
    
    # Optional
    trade_id: Optional[str] = Field(None, description="Exchange trade ID")
    is_buy_side_taker: Optional[bool] = Field(None, description="Was buyer the taker?")


# ─────────────────────────────────────────────────────────────
# FUNDAMENTAL & EXTERNAL DATA SCHEMAS
# ─────────────────────────────────────────────────────────────

class FundamentalsSnapshot(BaseModel):
    """
    Fundamental data snapshot.
    
    For fundamental analysis engine.
    """
    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Data timestamp (UTC)")
    
    # Valuation
    market_cap: Optional[float] = Field(None, gt=0)
    pe_ratio: Optional[float] = Field(None)
    pb_ratio: Optional[float] = Field(None)
    ps_ratio: Optional[float] = Field(None)
    peg_ratio: Optional[float] = Field(None)
    
    # Financials
    revenue: Optional[float] = Field(None, description="Annual revenue")
    ebitda: Optional[float] = Field(None)
    net_income: Optional[float] = Field(None)
    total_assets: Optional[float] = Field(None)
    total_debt: Optional[float] = Field(None)
    
    # Per Share
    eps: Optional[float] = Field(None)
    book_value_per_share: Optional[float] = Field(None)
    dividend_yield: Optional[float] = Field(None)
    
    # Technical Valuation
    beta: Optional[float] = Field(None)
    avg_volume_20d: Optional[float] = Field(None, ge=0)


class MacroEvent(BaseModel):
    """
    Macroeconomic event.
    
    For macro calendar and regime detection.
    """
    timestamp: datetime = Field(..., description="Event time (UTC)")
    event_name: str = Field(..., description="Event name")
    country: str = Field(..., description="Country code (e.g., 'US', 'CN')")
    
    # Impact
    impact: str = Field(..., description="Expected impact: high/medium/low")
    previous: Optional[float] = Field(None, description="Previous value")
    forecast: Optional[float] = Field(None, description="Consensus forecast")
    actual: Optional[float] = Field(None, description="Actual value")
    
    # Asset impact mapping
    affected_assets: list[str] = Field(
        default_factory=list, description="Affected symbols/indices"
    )
    
    # Surprise indicator
    is_surprise: Optional[bool] = Field(None, description="Actual vs forecast surprise")


class NewsEvent(BaseModel):
    """
    News headline/event.
    
    For sentiment analysis.
    """
    timestamp: datetime = Field(..., description="Publication time (UTC)")
    title: str = Field(..., description="Headline/title")
    source: str = Field(..., description="News source")
    url: Optional[str] = Field(None, description="Source URL")
    symbols: list[str] = Field(default_factory=list, description="Related symbols")
    
    # Sentiment
    sentiment_score: Optional[float] = Field(
        None, ge=-1, le=1, description="Sentiment: -1 (bear) to 1 (bull)"
    )
    sentiment_label: Optional[str] = Field(None, description="bullish/bearish/neutral")


class SentimentEvent(BaseModel):
    """
    Aggregated sentiment signal.
    
    Output of sentiment analysis engine.
    """
    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Analysis timestamp (UTC)")
    
    # Scores (all 0-1)
    news_sentiment: float = Field(0.5, ge=0, le=1)
    social_sentiment: float = Field(0.5, ge=0, le=1)
    forum_sentiment: float = Field(0.5, ge=0, le=1)
    analyst_sentiment: float = Field(0.5, ge=0, le=1)
    
    # Aggregated
    composite_sentiment: float = Field(0.5, ge=0, le=1, description="Weighted average")
    
    # Metrics
    bullish_ratio: float = Field(0.5, ge=0, le=1)
    bearish_ratio: float = Field(0.5, ge=0, le=1)
    neutral_ratio: float = Field(0.5, ge=0, le=1)
    
    # Metadata
    sources_count: int = Field(0, ge=0, description="Number of sources aggregated")
    metadata: dict = Field(default_factory=dict, description="Extended metadata for sentiment details")


# ─────────────────────────────────────────────────────────────
# ENGINE SIGNAL SCHEMAS
# ─────────────────────────────────────────────────────────────

class EngineSignal(BaseModel):
    """
    Output from any analysis engine.
    
    All engines MUST produce this schema.
    """
    engine_name: str = Field(..., description="Engine identifier (e.g., 'chan', 'technical')")
    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Signal timestamp (UTC)")
    timeframe: Optional[TimeFrame] = Field(None, description="Signal timeframe")
    
    # Signal components
    direction: Direction = Field(..., description="Signal direction")
    confidence: float = Field(0.5, ge=0, le=1, description="Confidence level")
    regime: Regime = Field(Regime.UNKNOWN, description="Detected regime")
    
    # Entry/Exit
    entry_score: float = Field(0.5, ge=0, le=1, description="Entry quality score")
    exit_score: float = Field(0.5, ge=0, le=1, description="Exit quality score")
    
    # Key levels
    entry_price: Optional[float] = Field(None, gt=0, description="Suggested entry price")
    stop_price: Optional[float] = Field(None, gt=0, description="Suggested stop price")
    target_price: Optional[float] = Field(None, gt=0, description="Suggested target price")
    
    # Risk/Reward
    risk_reward_ratio: Optional[float] = Field(None, ge=0, description="RR ratio")
    
    # Pattern/Label (for explainability)
    pattern_type: Optional[str] = Field(None, description="Detected pattern")
    pattern_name: Optional[str] = Field(None, description="Pattern name if any")
    
    # Metadata
    module_scores: dict[str, float] = Field(
        default_factory=dict, description="Component scores"
    )
    reasoning: str = Field("", description="Signal reasoning/description")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class ChanSignal(EngineSignal):
    """Specific signal from Chan Theory (缠论) engine."""
    # Structural
    fractal_level: Optional[str] = Field(None, description="Fractal: top/bottom")
    bi_status: Optional[str] = Field(None, description="笔 status")
    segment_status: Optional[str] = Field(None, description="线段 status")
    zhongshu_status: Optional[str] = Field(None, description="中枢 status")
    
    # Signals
    divergence: Optional[str] = Field(None, description="Divergence: bullish/bearish/none")
    purchase_point: Optional[int] = Field(None, description="Purchase point: 1/2/3")
    sell_point: Optional[int] = Field(None, description="Sell point: 1/2/3")
    
    # Multi-timeframe
    higher_tf_direction: Optional[Direction] = Field(None)
    lower_tf_direction: Optional[Direction] = Field(None)


class TechnicalSignal(EngineSignal):
    """Specific signal from classical technical analysis engine."""
    # Indicators
    trend: Optional[str] = Field(None, description="up/down/sideways")
    momentum: Optional[str] = Field(None, description="strengthening/weakening")
    volatility_state: Optional[str] = Field(None, description="contracting/expanding")
    
    # Patterns
    chart_pattern: Optional[str] = Field(None)
    candle_pattern: Optional[str] = Field(None)
    
    # Key levels detected
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)


class OrderFlowSignal(BaseModel):
    """
    Order flow analysis signal.
    
    NOT an EngineSignal - different schema for order book specifics.
    """
    symbol: str = Field(...)
    timestamp: datetime = Field(...)
    timeframe: TimeFrame = Field(...)
    
    # Imbalances
    book_imbalance: float = Field(0, description="-1 (heavy sell) to 1 (heavy buy)")
    bid_pressure: float = Field(0, description="Bid side pressure")
    ask_pressure: float = Field(0, description="Ask side pressure")
    
    # Delta
    delta: float = Field(0, description="Cumulative delta (buy volume - sell volume)")
    cum_delta: float = Field(0, description="Running cumulative delta")
    
    # Absorption
    absorption_score: float = Field(0, ge=0, le=1, description="Absorption detection")
    liquidity_sweep: bool = Field(False, description="Liquidity sweep detected")
    
    # Execution quality forecast
    expected_slippage: float = Field(0, ge=0, description="Expected slippage (bps)")
    execution_condition: ExecutionQuality = Field(ExecutionQuality.FAIR)
    
    # Levels
    stop_hunt_zones: list[tuple[float, float]] = Field(
        default_factory=list, description="[(low, high), ...]"
    )
    
    metadata: dict = Field(default_factory=dict)


class MacroSignal(BaseModel):
    """
    Macro regime signal.
    
    Output from macro analysis engine.
    """
    timestamp: datetime = Field(...)
    
    # Regime
    regime: Regime = Field(...)
    regime_confidence: float = Field(0.5, ge=0, le=1)
    
    # Themes
    dominant_themes: list[str] = Field(default_factory=list)
    risk_on: bool = Field(True, description="Risk appetite")
    
    # Asset allocation hints
    equity_bias: str = Field("neutral", description="bullish/bearish/neutral")
    bond_bias: str = Field("neutral")
    commodity_bias: str = Field("neutral")
    fx_bias: dict[str, str] = Field(default_factory=dict, description="{symbol: bias}")
    
    # Volatility
    vix_level: Optional[float] = Field(None, ge=0)
    move_level: Optional[float] = Field(None, ge=0)
    
    # Upcoming events
    high_impact_events: list[str] = Field(default_factory=list)
    
    metadata: dict = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# ARBITRATION SCHEMA
# ─────────────────────────────────────────────────────────────

class DecisionRationale(BaseModel):
    """Explainability snapshot for one signal in the arbitration chain."""

    signal_name: str = Field(..., description="Signal source name")
    direction: Direction = Field(..., description="Signal direction")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Raw confidence")
    weight: float = Field(..., ge=0.0, description="Applied weight")
    contribution: float = Field(..., description="Weighted contribution")
    rule_adjustments: list[str] = Field(default_factory=list)


class ConflictRecord(BaseModel):
    """Conflict-resolution snapshot for arbitration."""

    signal_a: str = Field(..., description="Conflicting signal A")
    signal_b: str = Field(..., description="Conflicting signal B")
    direction_a: Direction = Field(..., description="Direction for signal A")
    direction_b: Direction = Field(..., description="Direction for signal B")
    resolution: str = Field(..., description="How the conflict was resolved")
    rule_applied: str = Field(..., description="Rule used to resolve the conflict")


class ArbitrationDecision(BaseModel):
    """Unified arbitration contract used by Arbitration, Risk, Audit, and tests."""

    decision_id: str = Field(..., description="Unique decision ID (UUID)")
    timestamp: datetime = Field(..., description="Decision timestamp (UTC)")
    symbol: str = Field(..., description="Trading symbol")

    # Phase 6 core output
    bias: str = Field(
        "no_trade",
        description="no_trade/long_bias/short_bias/hold_bias/reduce_risk/exit_bias",
    )
    confidence: float = Field(..., ge=0, le=1)
    direction: Direction = Field(Direction.FLAT, description="Target direction")
    regime: Regime = Field(Regime.UNKNOWN, description="Detected regime")

    # Compatibility gates
    entry_permission: bool = Field(True, description="Whether entry is allowed")
    no_trade_reason: Optional[str] = Field(None, description="Why trade is blocked")
    max_position_pct: float = Field(0.1, ge=0, le=1)
    suggested_quantity: Optional[float] = Field(None, gt=0)

    # Execution hints
    execution_style: OrderType = Field(OrderType.MARKET)
    limit_price: Optional[float] = Field(None, gt=0)
    stop_price: Optional[float] = Field(None, gt=0)
    stop_logic: dict = Field(default_factory=dict)
    take_profit: Optional[float] = Field(None, gt=0)

    # Legacy/global aggregation fields
    engine_signals: dict[str, float] = Field(default_factory=dict)
    consensus_score: float = Field(0.5, ge=0, le=1)
    reasoning: str = Field("", description="Human-readable rationale")
    key_factors: list[str] = Field(default_factory=list)

    # Phase 6 explainability fields
    long_score: float = Field(0.0)
    short_score: float = Field(0.0)
    neutrality_score: float = Field(0.0)
    rationale: list[DecisionRationale] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    fundamental_reference: Optional[str] = Field(None)
    fundamental_veto_triggered: bool = Field(False)
    macro_regime: Optional[str] = Field(None)
    risk_adjustment: float = Field(1.0, ge=0.0, le=1.0)
    rules_applied: list[str] = Field(default_factory=list)
    signal_count: int = Field(0, ge=0)
    arbitration_latency_ms: float = Field(0.0, ge=0.0)

    # Audit bridge fields
    target_direction: Optional[str] = Field(None, description="Audit-oriented target direction")
    target_quantity: float = Field(0.0, ge=0)
    source_signals: list[dict] = Field(default_factory=list)
    signals: list[dict] = Field(default_factory=list)

    version: str = Field("1.0.0", description="Decision schema version")
    metadata: dict = Field(default_factory=dict)

    @property
    def no_trade_flag(self) -> bool:
        """Backward-compatible alias expected by older contract tests."""
        return self.bias == "no_trade" or not self.entry_permission


# ─────────────────────────────────────────────────────────────
# RISK SCHEMAS
# ─────────────────────────────────────────────────────────────

class RiskEvent(BaseModel):
    """
    Risk event/breach record.
    
    All risk events MUST be logged.
    """
    event_id: str = Field(..., description="Unique event ID")
    timestamp: datetime = Field(..., description="Event timestamp (UTC)")
    
    event_type: RiskEventType = Field(...)
    symbol: Optional[str] = Field(None, description="Affected symbol if any")
    
    # Details
    description: str = Field(...)
    triggered_value: float = Field(..., description="Actual value that triggered")
    threshold_value: float = Field(..., description="Threshold that was breached")
    
    # Action
    action_taken: str = Field(..., description="Risk action taken")
    position_closed: bool = Field(False, description="Was position closed?")
    order_cancelled: bool = Field(False, description="Was order cancelled?")
    
    # Context
    decision_id: Optional[str] = Field(None, description="Related decision if any")
    metadata: dict = Field(default_factory=dict)


class RiskLimits(BaseModel):
    """
    Risk limit configuration.
    
    These limits are enforced by the risk layer.
    """
    # Position limits
    max_position_pct: float = Field(0.1, gt=0, le=1)
    max_position_absolute: Optional[float] = Field(None, gt=0)
    max_positions: int = Field(10, ge=1)
    
    # Loss limits
    max_loss_pct_per_trade: float = Field(0.02, gt=0, le=1)
    max_loss_pct_per_day: float = Field(0.05, gt=0, le=1)
    max_drawdown_pct: float = Field(0.15, gt=0, le=1)
    
    # Exposure
    max_leverage: float = Field(1.0, ge=1)
    max_sector_exposure_pct: float = Field(0.3, gt=0, le=1)
    
    # Execution
    max_slippage_bps: float = Field(10, ge=0, description="Max slippage in bps")
    max_order_size_pct: float = Field(0.05, gt=0, le=1)
    
    # Correlation
    max_correlation: float = Field(0.7, gt=0, le=1)


# ─────────────────────────────────────────────────────────────
# EXECUTION SCHEMAS
# ─────────────────────────────────────────────────────────────

class ExecutionIntent(BaseModel):
    """
    Execution intent sent to execution layer.
    
    Derived from ArbitrationDecision + RiskLimits.
    """
    intent_id: str = Field(..., description="Unique intent ID")
    decision_id: str = Field(..., description="Source decision ID")
    timestamp: datetime = Field(...)
    
    symbol: str = Field(...)
    direction: Direction = Field(...)
    
    # Size
    quantity: float = Field(..., gt=0)
    price_limit: Optional[float] = Field(None, gt=0)
    
    # Order type
    order_type: OrderType = Field(...)
    
    # Execution parameters
    time_limit_seconds: Optional[int] = Field(None, gt=0)
    participation_rate: Optional[float] = Field(
        None, ge=0, le=1, description="For VWAP/POV execution"
    )
    
    # Algo params
    algo_params: dict = Field(default_factory=dict)
    
    # Risk overrides
    risk_adjusted: bool = Field(False)
    original_quantity: Optional[float] = Field(None, description="Before risk adjustment")
    
    metadata: dict = Field(default_factory=dict)


class OrderRecord(BaseModel):
    """
    Order record in the system.
    
    Full order lifecycle tracking.
    """
    order_id: str = Field(..., description="Internal order ID")
    decision_id: str = Field(..., description="Source decision ID")
    intent_id: Optional[str] = Field(None, description="Source intent ID")
    
    symbol: str = Field(...)
    timestamp: datetime = Field(..., description="Order creation time")
    
    # Order spec
    side: Side = Field(...)
    order_type: OrderType = Field(...)
    quantity: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)
    stop_price: Optional[float] = Field(None, gt=0)
    
    # Status tracking
    status: OrderStatus = Field(OrderStatus.PENDING)
    submitted_at: Optional[datetime] = Field(None)
    filled_at: Optional[datetime] = Field(None)
    cancelled_at: Optional[datetime] = Field(None)
    
    # Fill tracking
    filled_quantity: float = Field(0, ge=0)
    avg_fill_price: Optional[float] = Field(None, gt=0)
    
    # Execution quality
    slippage_bps: Optional[float] = Field(None, description="Slippage in bps")
    execution_quality: ExecutionQuality = Field(ExecutionQuality.GOOD)
    
    # Exchange
    exchange_order_id: Optional[str] = Field(None, description="Exchange order ID")
    exchange: Optional[str] = Field(None)
    
    metadata: dict = Field(default_factory=dict)


class FillRecord(BaseModel):
    """
    Individual fill record.
    
    One order may have multiple fills.
    """
    fill_id: str = Field(...)
    order_id: str = Field(...)
    
    timestamp: datetime = Field(...)
    
    price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    side: Side = Field(...)
    
    # Fees
    commission: float = Field(0, ge=0)
    commission_currency: str = Field("USD")
    
    # Quality
    is_maker: Optional[bool] = Field(None)
    liquidity_type: Optional[str] = Field(None, description="added/removed")
    
    exchange_fill_id: Optional[str] = Field(None)
    venue: Optional[str] = Field(None)


# ─────────────────────────────────────────────────────────────
# AUDIT SCHEMAS
# ─────────────────────────────────────────────────────────────

class AuditRecord(BaseModel):
    """
    Universal audit record.
    
    Every significant system event gets an audit record.
    """
    audit_id: str = Field(..., description="Unique audit ID")
    timestamp: datetime = Field(..., description="Event timestamp (UTC)")
    
    # What
    record_type: str = Field(..., description="Type: decision/execution/risk/config/...")  # noqa
    entity_type: str = Field(..., description="Entity: order/position/signal/...")
    entity_id: str = Field(..., description="Entity identifier")
    
    # Who/Where
    source: EventSource = Field(...)
    actor: str = Field("system", description="Who triggered: system/engine/user")
    
    # What happened
    action: str = Field(..., description="Action: created/updated/cancelled/...")
    before_state: Optional[dict] = Field(None, description="State before action")
    after_state: Optional[dict] = Field(None, description="State after action")
    
    # Why (for decisions)
    reason: Optional[str] = Field(None)
    
    # Context
    correlation_id: Optional[str] = Field(
        None, description="Links related events"
    )
    metadata: dict = Field(default_factory=dict)
    
    # Integrity
    checksum: Optional[str] = Field(None, description="For integrity verification")


# ─────────────────────────────────────────────────────────────
# POSITION & PORTFOLIO SCHEMAS
# ─────────────────────────────────────────────────────────────

class Position(BaseModel):
    """
    Current position state.
    """
    symbol: str = Field(...)
    timestamp: datetime = Field(...)
    
    # Position
    quantity: float = Field(0)
    side: Direction = Field(Direction.FLAT)
    avg_entry_price: float = Field(0, ge=0)
    
    # P&L
    unrealized_pnl: float = Field(0)
    realized_pnl: float = Field(0)
    pnl_pct: float = Field(0)
    
    # Risk
    exposure_pct: float = Field(0, ge=0)
    margin_used: float = Field(0, ge=0)
    
    metadata: dict = Field(default_factory=dict)


class Portfolio(BaseModel):
    """
    Portfolio state snapshot.
    """
    timestamp: datetime = Field(...)
    
    # Balance
    total_equity: float = Field(..., gt=0)
    cash: float = Field(..., ge=0)
    margin_used: float = Field(0, ge=0)
    
    # P&L
    daily_pnl: float = Field(0)
    daily_pnl_pct: float = Field(0)
    total_pnl: float = Field(0)
    total_pnl_pct: float = Field(0)
    
    # Drawdown
    current_drawdown: float = Field(0, le=0)
    peak_equity: float = Field(..., gt=0)
    
    # Positions
    positions: list[Position] = Field(default_factory=list)
    
    # Risk metrics
    leverage: float = Field(1.0, ge=1)
    beta_exposure: float = Field(0)
    
    metadata: dict = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# MODEL REGISTRY SCHEMAS
# ─────────────────────────────────────────────────────────────

class ModelMetadata(BaseModel):
    """
    Model version metadata.
    """
    model_id: str = Field(...)
    model_name: str = Field(...)
    version: str = Field(...)
    
    model_type: str = Field(..., description="e.g., 'xgboost', 'lightgbm', 'transformer'")
    
    created_at: datetime = Field(...)
    created_by: str = Field("system")
    
    # Training info
    training_start: Optional[datetime] = Field(None)
    training_end: Optional[datetime] = Field(None)
    training_samples: int = Field(0, ge=0)
    
    # Performance
    metrics: dict[str, float] = Field(default_factory=dict)
    
    # Status
    is_active: bool = Field(False)
    is_production: bool = Field(False)
    
    # Lineage
    parent_model_id: Optional[str] = Field(None)
    experiment_id: Optional[str] = Field(None)
    
    config: dict = Field(default_factory=dict)
    artifacts_path: Optional[str] = Field(None)
    
    metadata: dict = Field(default_factory=dict)


class ExperimentRecord(BaseModel):
    """
    Research experiment record.
    """
    experiment_id: str = Field(...)
    experiment_name: str = Field(...)
    
    started_at: datetime = Field(...)
    completed_at: Optional[datetime] = Field(None)
    status: str = Field("running", description="running/completed/failed/...")
    
    # Config
    config: dict = Field(default_factory=dict)
    
    # Results
    results: dict = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    
    # Models produced
    model_ids: list[str] = Field(default_factory=list)
    
    # Dataset
    dataset_version: Optional[str] = Field(None)
    
    metadata: dict = Field(default_factory=dict)
