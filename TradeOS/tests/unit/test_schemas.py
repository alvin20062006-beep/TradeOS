"""
Unit tests for core schemas.

Tests all Pydantic schema definitions for:
- Valid construction
- Invalid data rejection
- Field validation
- Serialization
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from ai_trading_tool.core.schemas import (
    # Enums
    TimeFrame,
    Side,
    OrderType,
    Direction,
    Regime,
    OrderStatus,
    ExecutionQuality,
    RiskEventType,
    
    # Market Data
    MarketBar,
    MarketTick,
    OrderBookSnapshot,
    TradePrint,
    
    # External Data
    FundamentalsSnapshot,
    MacroEvent,
    NewsEvent,
    SentimentEvent,
    
    # Signals
    EngineSignal,
    ChanSignal,
    TechnicalSignal,
    OrderFlowSignal,
    MacroSignal,
    
    # Decisions
    ArbitrationDecision,
    
    # Execution
    ExecutionIntent,
    OrderRecord,
    FillRecord,
    
    # Risk
    RiskEvent,
    RiskLimits,
    
    # Audit
    AuditRecord,
)


# ─────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def timestamp():
    return datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────
# ENUM TESTS
# ─────────────────────────────────────────────────────────────

class TestEnums:
    """Test enum values."""
    
    def test_timeframe_values(self):
        assert TimeFrame.M1.value == "1m"
        assert TimeFrame.H1.value == "1h"
        assert TimeFrame.D1.value == "1d"
    
    def test_direction_values(self):
        assert Direction.LONG.value == "long"
        assert Direction.SHORT.value == "short"
        assert Direction.FLAT.value == "flat"
    
    def test_regime_values(self):
        assert Regime.TRENDING_UP.value == "trending_up"
        assert Regime.RANGING.value == "ranging"
        assert Regime.VOLATILE.value == "volatile"


# ─────────────────────────────────────────────────────────────
# MARKET DATA SCHEMA TESTS
# ─────────────────────────────────────────────────────────────

class TestMarketBar:
    """Test MarketBar schema."""
    
    def test_valid_bar(self, timestamp):
        bar = MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M5,
            timestamp=timestamp,
            open=185.50,
            high=186.00,
            low=185.00,
            close=185.75,
            volume=150000,
        )
        assert bar.symbol == "AAPL"
        assert bar.timeframe == TimeFrame.M5
        assert bar.close == 185.75
        assert bar.high >= bar.low
    
    def test_invalid_high_less_than_open(self, timestamp):
        with pytest.raises(ValidationError):
            MarketBar(
                symbol="AAPL",
                timeframe=TimeFrame.M5,
                timestamp=timestamp,
                open=186.00,
                high=185.50,  # Invalid: high < open
                low=185.00,
                close=185.75,
                volume=150000,
            )
    
    def test_invalid_close_less_than_low(self, timestamp):
        with pytest.raises(ValidationError):
            MarketBar(
                symbol="AAPL",
                timeframe=TimeFrame.M5,
                timestamp=timestamp,
                open=185.50,
                high=186.00,
                low=186.00,
                close=185.50,  # Invalid: close < low
                volume=150000,
            )
    
    def test_optional_fields(self, timestamp):
        bar = MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M5,
            timestamp=timestamp,
            open=185.50,
            high=186.00,
            low=185.00,
            close=185.75,
            volume=150000,
            quote_volume=27_862_500,
            trades=1500,
            vwap=185.68,
        )
        assert bar.quote_volume == 27_862_500
        assert bar.trades == 1500
        assert bar.vwap == 185.68


class TestMarketTick:
    """Test MarketTick schema."""
    
    def test_valid_tick(self, timestamp):
        tick = MarketTick(
            symbol="AAPL",
            timestamp=timestamp,
            price=185.76,
            size=100,
            side=Side.BUY,
        )
        assert tick.price == 185.76
        assert tick.side == Side.BUY
    
    def test_tick_with_bid_ask(self, timestamp):
        tick = MarketTick(
            symbol="AAPL",
            timestamp=timestamp,
            price=185.76,
            size=100,
            bid=185.75,
            ask=185.77,
            bid_size=500,
            ask_size=400,
        )
        assert tick.bid == 185.75
        assert tick.ask == 185.77


class TestOrderBookSnapshot:
    """Test OrderBookSnapshot schema."""
    
    def test_valid_order_book(self, timestamp):
        obook = OrderBookSnapshot(
            symbol="AAPL",
            timestamp=timestamp,
            bids=[(185.75, 500), (185.74, 300)],
            asks=[(185.77, 400), (185.78, 250)],
        )
        assert len(obook.bids) == 2
        assert len(obook.asks) == 2
        assert obook.spread > 0
    
    def test_empty_levels(self, timestamp):
        obook = OrderBookSnapshot(
            symbol="AAPL",
            timestamp=timestamp,
            bids=[],
            asks=[],
        )
        assert len(obook.bids) == 0


class TestTradePrint:
    """Test TradePrint schema."""
    
    def test_valid_trade(self, timestamp):
        trade = TradePrint(
            symbol="AAPL",
            timestamp=timestamp,
            price=185.76,
            size=100,
            side=Side.BUY,
        )
        assert trade.side == Side.BUY


# ─────────────────────────────────────────────────────────────
# SIGNAL SCHEMA TESTS
# ─────────────────────────────────────────────────────────────

class TestEngineSignal:
    """Test EngineSignal schema."""
    
    def test_valid_signal(self, timestamp):
        signal = EngineSignal(
            engine_name="chan",
            symbol="AAPL",
            timestamp=timestamp,
            direction=Direction.LONG,
            confidence=0.75,
            regime=Regime.TRENDING_UP,
        )
        assert signal.engine_name == "chan"
        assert signal.confidence == 0.75
    
    def test_confidence_bounds(self, timestamp):
        # Valid: 0
        signal = EngineSignal(
            engine_name="chan",
            symbol="AAPL",
            timestamp=timestamp,
            direction=Direction.FLAT,
            confidence=0.0,
            regime=Regime.UNKNOWN,
        )
        assert signal.confidence == 0.0
        
        # Valid: 1
        signal.confidence = 1.0
        assert signal.confidence == 1.0
        
        # Invalid: > 1
        with pytest.raises(ValidationError):
            EngineSignal(
                engine_name="chan",
                symbol="AAPL",
                timestamp=timestamp,
                direction=Direction.LONG,
                confidence=1.5,  # Invalid
                regime=Regime.TRENDING_UP,
            )


class TestChanSignal:
    """Test ChanSignal schema."""
    
    def test_valid_chan_signal(self, timestamp):
        signal = ChanSignal(
            engine_name="chan",
            symbol="AAPL",
            timestamp=timestamp,
            direction=Direction.LONG,
            confidence=0.80,
            regime=Regime.TRENDING_UP,
            fractal_level="bottom",
            purchase_point=1,
            divergence="bullish",
        )
        assert signal.purchase_point == 1
        assert signal.divergence == "bullish"


class TestTechnicalSignal:
    """Test TechnicalSignal schema."""
    
    def test_valid_technical_signal(self, timestamp):
        signal = TechnicalSignal(
            engine_name="technical",
            symbol="AAPL",
            timestamp=timestamp,
            direction=Direction.LONG,
            confidence=0.70,
            regime=Regime.TRENDING_UP,
            trend="up",
            momentum="strengthening",
            support_levels=[185.00, 184.50],
            resistance_levels=[190.00, 191.00],
        )
        assert len(signal.support_levels) == 2
        assert signal.trend == "up"


class TestOrderFlowSignal:
    """Test OrderFlowSignal schema."""
    
    def test_valid_orderflow_signal(self, timestamp):
        signal = OrderFlowSignal(
            symbol="AAPL",
            timestamp=timestamp,
            timeframe=TimeFrame.M1,
            book_imbalance=0.3,
            bid_pressure=1500,
            ask_pressure=1000,
            delta=500,
            cum_delta=2500,
            absorption_score=0.5,
            liquidity_sweep=False,
            expected_slippage=2.5,
            execution_condition=ExecutionQuality.GOOD,
        )
        assert signal.book_imbalance == 0.3
        assert signal.execution_condition == ExecutionQuality.GOOD


# ─────────────────────────────────────────────────────────────
# DECISION SCHEMA TESTS
# ─────────────────────────────────────────────────────────────

class TestArbitrationDecision:
    """Test ArbitrationDecision schema."""
    
    def test_valid_decision(self, timestamp):
        decision = ArbitrationDecision(
            decision_id="test-uuid-123",
            timestamp=timestamp,
            symbol="AAPL",
            direction=Direction.LONG,
            confidence=0.78,
            regime=Regime.TRENDING_UP,
            entry_permission=True,
            max_position_pct=0.10,
            engine_signals={"chan": 0.75, "technical": 0.70},
            consensus_score=0.72,
            reasoning="Multi-engine consensus",
        )
        assert decision.decision_id == "test-uuid-123"
        assert decision.entry_permission is True
    
    def test_no_trade_decision(self, timestamp):
        decision = ArbitrationDecision(
            decision_id="test-uuid-456",
            timestamp=timestamp,
            symbol="AAPL",
            direction=Direction.FLAT,
            confidence=0.90,
            regime=Regime.VOLATILE,
            entry_permission=False,
            no_trade_reason="High volatility regime",
            max_position_pct=0.0,
            engine_signals={},
            consensus_score=0.50,
            reasoning="No trade due to regime",
        )
        assert decision.no_trade_flag is True
        assert decision.no_trade_reason == "High volatility regime"


# ─────────────────────────────────────────────────────────────
# EXECUTION SCHEMA TESTS
# ─────────────────────────────────────────────────────────────

class TestOrderRecord:
    """Test OrderRecord schema."""
    
    def test_valid_order(self, timestamp):
        order = OrderRecord(
            order_id="order-123",
            decision_id="decision-456",
            symbol="AAPL",
            timestamp=timestamp,
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=185.75,
            status=OrderStatus.PENDING,
        )
        assert order.quantity == 100
        assert order.status == OrderStatus.PENDING
    
    def test_order_status_transitions(self, timestamp):
        order = OrderRecord(
            order_id="order-123",
            decision_id="decision-456",
            symbol="AAPL",
            timestamp=timestamp,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            status=OrderStatus.PENDING,
        )
        # Simulate transition
        order.status = OrderStatus.SUBMITTED
        assert order.status == OrderStatus.SUBMITTED
        
        order.status = OrderStatus.FILLED
        order.filled_quantity = 100
        order.avg_fill_price = 185.77
        assert order.status == OrderStatus.FILLED


class TestFillRecord:
    """Test FillRecord schema."""
    
    def test_valid_fill(self, timestamp):
        fill = FillRecord(
            fill_id="fill-123",
            order_id="order-456",
            timestamp=timestamp,
            price=185.77,
            quantity=100,
            side=Side.BUY,
            commission=0.25,
        )
        assert fill.commission == 0.25
        assert fill.is_maker is None  # Optional


# ─────────────────────────────────────────────────────────────
# RISK SCHEMA TESTS
# ─────────────────────────────────────────────────────────────

class TestRiskEvent:
    """Test RiskEvent schema."""
    
    def test_valid_risk_event(self, timestamp):
        event = RiskEvent(
            event_id="risk-123",
            timestamp=timestamp,
            event_type=RiskEventType.MAX_POSITION_BREACH,
            symbol="AAPL",
            description="Position exceeded 15%",
            triggered_value=0.18,
            threshold_value=0.15,
            action_taken="Reduced to 10%",
        )
        assert event.event_type == RiskEventType.MAX_POSITION_BREACH
        assert event.triggered_value > event.threshold_value


class TestRiskLimits:
    """Test RiskLimits schema."""
    
    def test_default_limits(self):
        limits = RiskLimits()
        assert limits.max_position_pct == 0.10
        assert limits.max_positions == 10
        assert limits.max_loss_pct_per_trade == 0.02
    
    def test_custom_limits(self):
        limits = RiskLimits(
            max_position_pct=0.15,
            max_positions=20,
            max_leverage=2.0,
        )
        assert limits.max_position_pct == 0.15
        assert limits.max_leverage == 2.0


# ─────────────────────────────────────────────────────────────
# SERIALIZATION TESTS
# ─────────────────────────────────────────────────────────────

class TestSerialization:
    """Test schema serialization."""
    
    def test_bar_to_dict(self, timestamp):
        bar = MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M5,
            timestamp=timestamp,
            open=185.50,
            high=186.00,
            low=185.00,
            close=185.75,
            volume=150000,
        )
        data = bar.model_dump()
        assert data["symbol"] == "AAPL"
        assert data["close"] == 185.75
    
    def test_bar_to_json(self, timestamp):
        bar = MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M5,
            timestamp=timestamp,
            open=185.50,
            high=186.00,
            low=185.00,
            close=185.75,
            volume=150000,
        )
        json_str = bar.model_dump_json()
        assert "AAPL" in json_str
        assert "185.75" in json_str
    
    def test_from_dict(self, timestamp):
        data = {
            "symbol": "AAPL",
            "timeframe": "5m",
            "timestamp": timestamp.isoformat(),
            "open": 185.50,
            "high": 186.00,
            "low": 185.00,
            "close": 185.75,
            "volume": 150000,
        }
        bar = MarketBar.model_validate(data)
        assert bar.symbol == "AAPL"
