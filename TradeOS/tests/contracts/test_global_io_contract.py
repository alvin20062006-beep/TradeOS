"""
Contract tests for global I/O schemas.

These tests verify that all schemas exist and have the required fields,
ensuring the I/O contract is maintained across the platform.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4


class TestSchemaExistence:
    """Verify all schemas can be imported."""
    
    def test_market_data_schemas_exist(self):
        """All market data schemas should exist."""
        from ai_trading_tool.core.schemas import (
            MarketBar,
            MarketTick,
            OrderBookSnapshot,
            TradePrint,
        )
        assert MarketBar is not None
        assert MarketTick is not None
        assert OrderBookSnapshot is not None
        assert TradePrint is not None
    
    def test_external_data_schemas_exist(self):
        """All external data schemas should exist."""
        from ai_trading_tool.core.schemas import (
            FundamentalsSnapshot,
            MacroEvent,
            NewsEvent,
            SentimentEvent,
        )
        assert FundamentalsSnapshot is not None
        assert MacroEvent is not None
        assert NewsEvent is not None
        assert SentimentEvent is not None
    
    def test_signal_schemas_exist(self):
        """All signal schemas should exist."""
        from ai_trading_tool.core.schemas import (
            EngineSignal,
            ChanSignal,
            TechnicalSignal,
            OrderFlowSignal,
            MacroSignal,
        )
        assert EngineSignal is not None
        assert ChanSignal is not None
        assert TechnicalSignal is not None
        assert OrderFlowSignal is not None
        assert MacroSignal is not None
    
    def test_decision_schemas_exist(self):
        """Decision schemas should exist."""
        from ai_trading_tool.core.schemas import (
            ArbitrationDecision,
        )
        assert ArbitrationDecision is not None
    
    def test_execution_schemas_exist(self):
        """Execution schemas should exist."""
        from ai_trading_tool.core.schemas import (
            ExecutionIntent,
            OrderRecord,
            FillRecord,
        )
        assert ExecutionIntent is not None
        assert OrderRecord is not None
        assert FillRecord is not None
    
    def test_risk_schemas_exist(self):
        """Risk schemas should exist."""
        from ai_trading_tool.core.schemas import (
            RiskEvent,
            RiskLimits,
        )
        assert RiskEvent is not None
        assert RiskLimits is not None
    
    def test_audit_schemas_exist(self):
        """Audit schemas should exist."""
        from ai_trading_tool.core.schemas import (
            AuditRecord,
        )
        assert AuditRecord is not None


class TestSchemaFields:
    """Verify schemas have all required fields."""
    
    def test_market_bar_required_fields(self):
        """MarketBar should have all required fields."""
        from ai_trading_tool.core.schemas import MarketBar, TimeFrame
        
        bar = MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M5,
            timestamp=datetime.now(timezone.utc),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
        )
        
        # Check all fields exist
        assert hasattr(bar, "symbol")
        assert hasattr(bar, "timeframe")
        assert hasattr(bar, "timestamp")
        assert hasattr(bar, "open")
        assert hasattr(bar, "high")
        assert hasattr(bar, "low")
        assert hasattr(bar, "close")
        assert hasattr(bar, "volume")
    
    def test_engine_signal_required_fields(self):
        """EngineSignal should have all required fields."""
        from ai_trading_tool.core.schemas import EngineSignal, Direction, Regime
        
        signal = EngineSignal(
            engine_name="test",
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            direction=Direction.LONG,
            confidence=0.5,
            regime=Regime.TRENDING_UP,
        )
        
        assert hasattr(signal, "engine_name")
        assert hasattr(signal, "symbol")
        assert hasattr(signal, "timestamp")
        assert hasattr(signal, "direction")
        assert hasattr(signal, "confidence")
        assert hasattr(signal, "regime")
        assert hasattr(signal, "reasoning")
        assert hasattr(signal, "metadata")
    
    def test_arbitration_decision_required_fields(self):
        """ArbitrationDecision should have all required fields."""
        from ai_trading_tool.core.schemas import ArbitrationDecision, Direction, Regime
        
        decision = ArbitrationDecision(
            decision_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            symbol="AAPL",
            direction=Direction.LONG,
            confidence=0.5,
            regime=Regime.TRENDING_UP,
            entry_permission=True,
            max_position_pct=0.1,
            engine_signals={},
            consensus_score=0.5,
            reasoning="test",
        )
        
        assert hasattr(decision, "decision_id")
        assert hasattr(decision, "direction")
        assert hasattr(decision, "confidence")
        assert hasattr(decision, "entry_permission")
        assert hasattr(decision, "max_position_pct")
        assert hasattr(decision, "engine_signals")
        assert hasattr(decision, "consensus_score")
        assert hasattr(decision, "no_trade_flag")
    
    def test_order_record_required_fields(self):
        """OrderRecord should have all required fields."""
        from ai_trading_tool.core.schemas import OrderRecord, Side, OrderType, OrderStatus
        
        order = OrderRecord(
            order_id=str(uuid4()),
            decision_id=str(uuid4()),
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            status=OrderStatus.PENDING,
        )
        
        assert hasattr(order, "order_id")
        assert hasattr(order, "decision_id")
        assert hasattr(order, "side")
        assert hasattr(order, "order_type")
        assert hasattr(order, "quantity")
        assert hasattr(order, "status")
        assert hasattr(order, "filled_quantity")
    
    def test_risk_event_required_fields(self):
        """RiskEvent should have all required fields."""
        from ai_trading_tool.core.schemas import RiskEvent, RiskEventType
        
        event = RiskEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            event_type=RiskEventType.MAX_POSITION_BREACH,
            description="test",
            triggered_value=0.18,
            threshold_value=0.15,
            action_taken="reduced",
        )
        
        assert hasattr(event, "event_id")
        assert hasattr(event, "event_type")
        assert hasattr(event, "description")
        assert hasattr(event, "triggered_value")
        assert hasattr(event, "threshold_value")
        assert hasattr(event, "action_taken")


class TestSchemaEnums:
    """Verify all enums exist and have expected values."""
    
    def test_direction_enum(self):
        from ai_trading_tool.core.schemas import Direction
        assert "long" in [d.value for d in Direction]
        assert "short" in [d.value for d in Direction]
        assert "flat" in [d.value for d in Direction]
    
    def test_side_enum(self):
        from ai_trading_tool.core.schemas import Side
        assert "buy" in [s.value for s in Side]
        assert "sell" in [s.value for s in Side]
    
    def test_order_type_enum(self):
        from ai_trading_tool.core.schemas import OrderType
        expected = ["market", "limit", "stop", "stop_limit", "twap", "vwap", "pov", "iceberg", "adaptive"]
        for ot in expected:
            assert ot in [o.value for o in OrderType]
    
    def test_regime_enum(self):
        from ai_trading_tool.core.schemas import Regime
        expected = ["trending_up", "trending_down", "ranging", "volatile", "unknown"]
        for r in expected:
            assert r in [reg.value for reg in Regime]
    
    def test_timeframe_enum(self):
        from ai_trading_tool.core.schemas import TimeFrame
        expected = ["1s", "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
        for tf in expected:
            assert tf in [t.value for t in TimeFrame]


class TestSchemaValidation:
    """Test schema validation rules."""
    
    def test_direction_validation(self):
        from ai_trading_tool.core.schemas import Direction
        # Should accept valid values
        assert Direction("long") == Direction.LONG
        assert Direction("short") == Direction.SHORT
        assert Direction("flat") == Direction.FLAT
    
    def test_timeframe_validation(self):
        from ai_trading_tool.core.schemas import TimeFrame
        assert TimeFrame("5m") == TimeFrame.M5
        assert TimeFrame("1h") == TimeFrame.H1
        assert TimeFrame("1d") == TimeFrame.D1
    
    def test_confidence_bounds(self):
        from ai_trading_tool.core.schemas import EngineSignal, Direction, Regime
        from pydantic import ValidationError
        
        # Should accept 0-1 range
        signal = EngineSignal(
            engine_name="test",
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            direction=Direction.LONG,
            confidence=0.0,
            regime=Regime.TRENDING_UP,
        )
        assert signal.confidence == 0.0
        
        signal = EngineSignal(
            engine_name="test",
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            direction=Direction.LONG,
            confidence=1.0,
            regime=Regime.TRENDING_UP,
        )
        assert signal.confidence == 1.0
        
        # Should reject out of range
        with pytest.raises(ValidationError):
            EngineSignal(
                engine_name="test",
                symbol="AAPL",
                timestamp=datetime.now(timezone.utc),
                direction=Direction.LONG,
                confidence=1.5,  # Invalid
                regime=Regime.TRENDING_UP,
            )


class TestSchemaCompleteness:
    """Meta-tests to ensure schema contract is complete."""
    
    def test_all_phase1_schemas_defined(self):
        """Verify all Phase 1 schemas are defined."""
        required_schemas = [
            # Market data
            "MarketBar",
            "MarketTick", 
            "OrderBookSnapshot",
            "TradePrint",
            # External data
            "FundamentalsSnapshot",
            "MacroEvent",
            "NewsEvent",
            "SentimentEvent",
            # Signals
            "EngineSignal",
            "ArbitrationDecision",
            # Execution
            "ExecutionIntent",
            "OrderRecord",
            "FillRecord",
            # Risk
            "RiskEvent",
            "RiskLimits",
            # Audit
            "AuditRecord",
        ]
        
        from ai_trading_tool.core import schemas as schemas_module
        
        for schema_name in required_schemas:
            assert hasattr(schemas_module, schema_name), f"Missing schema: {schema_name}"
    
    def test_no_adhoc_dict_pattern(self):
        """Verify that EngineSignal properly captures all signal data."""
        from ai_trading_tool.core.schemas import EngineSignal, Direction, Regime
        
        # This test ensures we're using schemas, not ad-hoc dicts
        signal = EngineSignal(
            engine_name="chan",
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            direction=Direction.LONG,
            confidence=0.75,
            regime=Regime.TRENDING_UP,
            module_scores={"fractal": 0.9, "stroke": 0.8},
            metadata={"custom": "data"},
        )
        
        # Should have typed fields, not just raw dict
        assert isinstance(signal.module_scores, dict)
        assert signal.module_scores["fractal"] == 0.9
