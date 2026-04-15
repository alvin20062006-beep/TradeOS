"""
Test configuration and fixtures for AI Trading Tool.

This file provides:
- Pytest configuration
- Shared fixtures
- Schema validation helpers
- Test database setup
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Generator
from uuid import uuid4

import pytest
from pydantic import ValidationError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ─────────────────────────────────────────────────────────────
# PROJECT FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def config_path(project_root: Path) -> Path:
    """Return config directory path."""
    return project_root / "config"


@pytest.fixture
def mock_timestamp() -> datetime:
    """Return a fixed timestamp for testing."""
    return datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────
# PERSISTENCE FIXTURES
# ─────────────────────────────────────────────────────────────

class FakeModel:
    """
    Module-level fake model for pickle roundtrip tests.
    Defined at module level (not inside a test function) so that
    pickle can resolve the class by __module__ + __qualname__.
    """
    coefficient = 1.5

    def predict(self, X):
        return X


# ─────────────────────────────────────────────────────────────
# SCHEMA FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_market_bar(mock_timestamp):
    """Return a sample MarketBar."""
    from ai_trading_tool.core.schemas import MarketBar, TimeFrame
    
    return MarketBar(
        symbol="AAPL",
        timeframe=TimeFrame.M5,
        timestamp=mock_timestamp,
        open=185.50,
        high=186.00,
        low=185.25,
        close=185.75,
        volume=150000,
        quote_volume=27_862_500,
        trades=1500,
        vwap=185.68,
        source="yfinance",
    )


@pytest.fixture
def sample_order_book(mock_timestamp):
    """Return a sample OrderBookSnapshot."""
    from ai_trading_tool.core.schemas import OrderBookSnapshot
    
    return OrderBookSnapshot(
        symbol="AAPL",
        timestamp=mock_timestamp,
        bids=[(185.75, 500), (185.74, 300), (185.73, 200)],
        asks=[(185.77, 400), (185.78, 250), (185.79, 300)],
        bid_depth=1000,
        ask_depth=950,
        spread=0.02,
        mid_price=185.76,
        imbalance=0.025,
    )


@pytest.fixture
def sample_engine_signal(mock_timestamp):
    """Return a sample EngineSignal."""
    from ai_trading_tool.core.schemas import EngineSignal, Direction, Regime, TimeFrame
    
    return EngineSignal(
        engine_name="chan",
        symbol="AAPL",
        timestamp=mock_timestamp,
        timeframe=TimeFrame.M5,
        direction=Direction.LONG,
        confidence=0.75,
        regime=Regime.TRENDING_UP,
        entry_score=0.80,
        exit_score=0.40,
        entry_price=185.75,
        stop_price=184.50,
        target_price=190.00,
        risk_reward_ratio=2.5,
        pattern_type="chan_first_buy",
        pattern_name="缠论一买",
        module_scores={"fractal": 0.9, "stroke": 0.8, "zhongshu": 0.7},
        reasoning="缠论一买信号，配合高置信度",
        metadata={"level": 1},
    )


@pytest.fixture
def sample_arbitration_decision(mock_timestamp):
    """Return a sample ArbitrationDecision."""
    from ai_trading_tool.core.schemas import (
        ArbitrationDecision, Direction, Regime, OrderType
    )
    
    return ArbitrationDecision(
        decision_id=str(uuid4()),
        timestamp=mock_timestamp,
        symbol="AAPL",
        direction=Direction.LONG,
        confidence=0.78,
        regime=Regime.TRENDING_UP,
        entry_permission=True,
        no_trade_reason=None,
        max_position_pct=0.10,
        suggested_quantity=100,
        execution_style=OrderType.LIMIT,
        limit_price=185.75,
        stop_price=184.50,
        stop_logic={"type": "fixed", "price": 184.50},
        take_profit=190.00,
        engine_signals={
            "chan": 0.75,
            "technical": 0.70,
            "orderflow": 0.80,
            "sentiment": 0.65,
            "macro": 0.60,
            "qlib": 0.85,
        },
        consensus_score=0.72,
        reasoning="多引擎共振，缠论一买配合Qlib信号",
        key_factors=["chan_signal", "qlib_confirm", "low_volatility"],
    )


@pytest.fixture
def sample_order_record(mock_timestamp):
    """Return a sample OrderRecord."""
    from ai_trading_tool.core.schemas import OrderRecord, OrderStatus, OrderType, Side
    
    return OrderRecord(
        order_id=str(uuid4()),
        decision_id=str(uuid4()),
        symbol="AAPL",
        timestamp=mock_timestamp,
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=185.75,
        stop_price=184.50,
        status=OrderStatus.FILLED,
        submitted_at=mock_timestamp,
        filled_at=mock_timestamp,
        filled_quantity=100,
        avg_fill_price=185.77,
        slippage_bps=1.08,
        execution_quality="good",
        exchange_order_id="EX12345",
        exchange="NASDAQ",
    )


@pytest.fixture
def sample_risk_event(mock_timestamp):
    """Return a sample RiskEvent."""
    from ai_trading_tool.core.schemas import RiskEvent, RiskEventType
    
    return RiskEvent(
        event_id=str(uuid4()),
        timestamp=mock_timestamp,
        event_type=RiskEventType.MAX_POSITION_BREACH,
        symbol="AAPL",
        description="Position exceeded max allowed",
        triggered_value=0.18,
        threshold_value=0.15,
        action_taken="Reduced to 10%",
        position_closed=False,
        order_cancelled=False,
        decision_id=str(uuid4()),
    )


# ─────────────────────────────────────────────────────────────
# TEST HELPERS
# ─────────────────────────────────────────────────────────────

class SchemaValidator:
    """Helper class for schema validation testing."""
    
    @staticmethod
    def assert_valid(schema_class, data: dict):
        """Assert that data is valid for schema."""
        try:
            instance = schema_class(**data)
            assert instance is not None
            return instance
        except ValidationError as e:
            pytest.fail(f"Validation failed: {e}")
    
    @staticmethod
    def assert_invalid(schema_class, data: dict, field: str = None):
        """Assert that data is invalid for schema."""
        with pytest.raises(ValidationError) as exc_info:
            schema_class(**data)
        
        if field:
            errors = exc_info.value.errors()
            assert any(e["loc"] == (field,) for e in errors), \
                f"Expected validation error for field '{field}'"


class MarketDataFactory:
    """Factory for generating market data for testing."""
    
    @staticmethod
    def create_bar(
        symbol: str = "AAPL",
        timeframe: str = "5m",
        close: float = 185.75,
        **overrides,
    ):
        """Create a MarketBar with sensible defaults."""
        from ai_trading_tool.core.schemas import MarketBar, TimeFrame
        
        # Create valid OHLC based on close
        high = close * 1.005
        low = close * 0.995
        open_price = (high + low) / 2
        
        data = {
            "symbol": symbol,
            "timeframe": TimeFrame(timeframe),
            "timestamp": datetime.now(timezone.utc),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100000,
        }
        data.update(overrides)
        
        return MarketBar(**data)
    
    @staticmethod
    def create_trend_bars(
        symbol: str,
        direction: str = "up",
        count: int = 10,
        timeframe: str = "5m",
    ):
        """Create a series of trending bars."""
        from ai_trading_tool.core.schemas import MarketBar, TimeFrame
        
        bars = []
        base_price = 185.0
        step = 0.5 if direction == "up" else -0.5
        
        for i in range(count):
            close = base_price + (step * i)
            high = close * 1.003
            low = close * 0.997
            open_price = (high + low) / 2
            
            bar = MarketBar(
                symbol=symbol,
                timeframe=TimeFrame(timeframe),
                timestamp=datetime.now(timezone.utc),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=100000 + (i * 1000),
            )
            bars.append(bar)
        
        return bars


# ─────────────────────────────────────────────────────────────
# PYTEST CONFIGURATION
# ─────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests across modules"
    )
    config.addinivalue_line(
        "markers", "contract: Schema contract tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )
    config.addinivalue_line(
        "markers", "requires_data: Tests requiring market data"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    # Add markers based on test location
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "contracts" in str(item.fspath):
            item.add_marker(pytest.mark.contract)


# ─────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────

__all__ = [
    "SchemaValidator",
    "MarketDataFactory",
    "sample_market_bar",
    "sample_order_book",
    "sample_engine_signal",
    "sample_arbitration_decision",
    "sample_order_record",
    "sample_risk_event",
    "mock_timestamp",
]
