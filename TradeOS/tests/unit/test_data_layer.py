"""
Data Layer Tests

Comprehensive tests for:
- Provider contracts
- Storage round-trip
- Schema validation
- Backfill resume
- Replay functionality
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator

import pytest
import pandas as pd

from ai_trading_tool.core.data import (
    # Schemas
    get_schema_type,
    list_schema_types,
    SCHEMA_TYPES,
    
    # Base
    DataDomain,
    DataProvider,
    MarketDataProvider,
    
    # Storage
    DataStore,
    
    # Validation
    ValidationIssue,
    BarValidator,
    TickValidator,
    OrderBookValidator,
    FundamentalsValidator,
    EventValidator,
    DataValidator,
    
    # Replay
    ReplayConfig,
    HistoricalReplay,
    BarReplayReader,
    
    # Backfill
    BackfillManager,
    
    # Registry
    DataProviderRegistry,
)
from ai_trading_tool.core.schemas import (
    MarketBar,
    MarketTick,
    OrderBookSnapshot,
    TradePrint,
    FundamentalsSnapshot,
    MacroEvent,
    NewsEvent,
    SentimentEvent,
    TimeFrame,
    Side,
)


# ─────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_bars():
    """Create sample OHLCV bars."""
    base_time = datetime(2024, 1, 1, 9, 30)
    bars = []
    
    for i in range(10):
        timestamp = base_time + timedelta(minutes=i)
        bars.append(MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M1,
            timestamp=timestamp,
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1000 + i * 100,
            source="test",
        ))
    
    return bars


@pytest.fixture
def sample_ticks():
    """Create sample tick data."""
    base_time = datetime(2024, 1, 1, 9, 30)
    ticks = []
    
    for i in range(10):
        timestamp = base_time + timedelta(seconds=i)
        ticks.append(MarketTick(
            symbol="AAPL",
            timestamp=timestamp,
            price=100.0 + i * 0.01,
            size=100,
            side=Side.BUY if i % 2 == 0 else Side.SELL,
            bid=99.99,
            ask=100.01,
        ))
    
    return ticks


@pytest.fixture
def sample_order_book():
    """Create sample order book snapshot."""
    return OrderBookSnapshot(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 1, 9, 30),
        bids=[(100.0, 500), (99.99, 1000), (99.98, 1500)],
        asks=[(100.01, 400), (100.02, 800), (100.03, 1200)],
        bid_depth=3000,
        ask_depth=2400,
        spread=0.01,
        mid_price=100.005,
        imbalance=0.1,
    )


@pytest.fixture
def sample_fundamentals():
    """Create sample fundamentals snapshot."""
    return FundamentalsSnapshot(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 1),
        market_cap=3_000_000_000_000,
        pe_ratio=25.5,
        pb_ratio=8.2,
        ps_ratio=7.1,
        revenue=394_000_000_000,
        eps=6.05,
        dividend_yield=0.005,
        beta=1.2,
    )


@pytest.fixture
def sample_macro_event():
    """Create sample macro event."""
    return MacroEvent(
        timestamp=datetime(2024, 1, 1, 8, 30),
        event_name="Non-Farm Payrolls",
        country="US",
        impact="high",
        previous=200000,
        forecast=210000,
        actual=215000,
        affected_assets=["SPY", "QQQ", "USD"],
        is_surprise=True,
    )


@pytest.fixture
def sample_news_event():
    """Create sample news event."""
    return NewsEvent(
        timestamp=datetime(2024, 1, 1, 9, 0),
        title="Apple announces record earnings",
        source="Reuters",
        url="https://example.com/news/1",
        symbols=["AAPL"],
        sentiment_score=0.8,
        sentiment_label="bullish",
    )


@pytest.fixture
def sample_sentiment_event():
    """Create sample sentiment event."""
    return SentimentEvent(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 1, 9, 0),
        news_sentiment=0.7,
        social_sentiment=0.6,
        forum_sentiment=0.5,
        analyst_sentiment=0.8,
        composite_sentiment=0.65,
        bullish_ratio=0.6,
        bearish_ratio=0.2,
        neutral_ratio=0.2,
        sources_count=10,
    )


# ─────────────────────────────────────────────────────────────
# SCHEMA TESTS
# ─────────────────────────────────────────────────────────────

class TestSchemas:
    """Test schema definitions and utilities."""
    
    def test_list_schema_types(self):
        """Test listing all schema types."""
        types = list_schema_types()
        assert "bars" in types
        assert "ticks" in types
        assert "orderbooks" in types
        assert "trades" in types
        assert "fundamentals" in types
        assert "macro" in types
        assert "news" in types
        assert "sentiment" in types
        assert len(types) == 8
    
    def test_get_schema_type(self):
        """Test getting schema type by name."""
        assert get_schema_type("bars") == MarketBar
        assert get_schema_type("ticks") == MarketTick
        assert get_schema_type("orderbooks") == OrderBookSnapshot
        assert get_schema_type("fundamentals") == FundamentalsSnapshot
        assert get_schema_type("macro") == MacroEvent
        assert get_schema_type("news") == NewsEvent
        assert get_schema_type("sentiment") == SentimentEvent
    
    def test_schema_type_registry(self):
        """Test schema type registry contents."""
        assert len(SCHEMA_TYPES) == 8
        assert all(isinstance(k, str) for k in SCHEMA_TYPES.keys())


# ─────────────────────────────────────────────────────────────
# VALIDATOR TESTS
# ─────────────────────────────────────────────────────────────

class TestBarValidator:
    """Test OHLCV bar validation."""
    
    def test_valid_bar(self, sample_bars):
        """Test validation of valid bars."""
        validator = BarValidator()
        issues = validator.validate(sample_bars[0])
        assert len(issues) == 0
    
    def test_invalid_ohlc(self):
        """Test detection of invalid OHLC."""
        validator = BarValidator()
        
        bar = MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M1,
            timestamp=datetime.now(),
            open=100,
            high=98,  # Invalid: high < low
            low=99,
            close=100,
            volume=1000,
        )
        
        issues = validator.validate(bar)
        assert len(issues) > 0
        assert any(i.issue_type == "invalid_ohlc" for i in issues)
    
    def test_negative_price(self):
        """Test detection of negative prices."""
        validator = BarValidator()
        
        bar = MarketBar(
            symbol="AAPL",
            timeframe=TimeFrame.M1,
            timestamp=datetime.now(),
            open=-100,  # Invalid
            high=100,
            low=99,
            close=100,
            volume=1000,
        )
        
        issues = validator.validate(bar)
        assert any(i.issue_type == "invalid_price" for i in issues)
    
    def test_sequence_validation(self, sample_bars):
        """Test validation of bar sequences."""
        validator = BarValidator()
        
        # Create gap
        bars = sample_bars[:3] + sample_bars[5:]
        
        issues = validator.validate_sequence(bars)
        assert any(i.issue_type == "time_gap" for i in issues)


class TestTickValidator:
    """Test tick data validation."""
    
    def test_valid_tick(self, sample_ticks):
        """Test validation of valid ticks."""
        validator = TickValidator()
        issues = validator.validate(sample_ticks[0])
        assert len(issues) == 0
    
    def test_invalid_price(self):
        """Test detection of invalid tick price."""
        validator = TickValidator()
        
        tick = MarketTick(
            symbol="AAPL",
            timestamp=datetime.now(),
            price=-100,  # Invalid
            size=100,
        )
        
        issues = validator.validate(tick)
        assert any(i.issue_type == "invalid_price" for i in issues)
    
    def test_invalid_spread(self):
        """Test detection of invalid bid/ask spread."""
        validator = TickValidator()
        
        tick = MarketTick(
            symbol="AAPL",
            timestamp=datetime.now(),
            price=100,
            size=100,
            bid=101,  # Invalid: bid > ask
            ask=100,
        )
        
        issues = validator.validate(tick)
        assert any(i.issue_type == "invalid_spread" for i in issues)


class TestOrderBookValidator:
    """Test order book validation."""
    
    def test_valid_order_book(self, sample_order_book):
        """Test validation of valid order book."""
        validator = OrderBookValidator()
        issues = validator.validate(sample_order_book)
        assert len(issues) == 0
    
    def test_crossed_book(self):
        """Test detection of crossed book."""
        validator = OrderBookValidator()
        
        snapshot = OrderBookSnapshot(
            symbol="AAPL",
            timestamp=datetime.now(),
            bids=[(101.0, 500)],  # Bid > Ask
            asks=[(100.0, 400)],
            bid_depth=500,
            ask_depth=400,
            spread=-1.0,
            mid_price=100.5,
            imbalance=0.0,
        )
        
        issues = validator.validate(snapshot)
        assert any(i.issue_type == "crossed_book" for i in issues)


class TestFundamentalsValidator:
    """Test fundamentals validation."""
    
    def test_valid_fundamentals(self, sample_fundamentals):
        """Test validation of valid fundamentals."""
        validator = FundamentalsValidator()
        issues = validator.validate(sample_fundamentals)
        assert len(issues) == 0
    
    def test_extreme_pe_ratio(self):
        """Test detection of extreme P/E ratio."""
        validator = FundamentalsValidator()
        
        fundamentals = FundamentalsSnapshot(
            symbol="AAPL",
            timestamp=datetime.now(),
            pe_ratio=5000,  # Extreme
        )
        
        issues = validator.validate(fundamentals)
        assert any(i.issue_type == "extreme_pe_ratio" for i in issues)


class TestEventValidator:
    """Test event validation."""
    
    def test_valid_macro_event(self, sample_macro_event):
        """Test validation of valid macro event."""
        validator = EventValidator()
        issues = validator.validate_macro(sample_macro_event)
        assert len(issues) == 0
    
    def test_invalid_impact_level(self):
        """Test detection of invalid impact level."""
        validator = EventValidator()
        
        event = MacroEvent(
            timestamp=datetime.now(),
            event_name="Test",
            country="US",
            impact="extreme",  # Invalid
        )
        
        issues = validator.validate_macro(event)
        assert any(i.issue_type == "invalid_impact_level" for i in issues)
    
    def test_sentiment_out_of_range(self):
        """Test detection of out-of-range sentiment."""
        validator = EventValidator()
        
        event = NewsEvent(
            timestamp=datetime.now(),
            title="Test",
            source="Test",
            sentiment_score=2.0,  # Out of range
        )
        
        issues = validator.validate_news(event)
        assert any(i.issue_type == "sentiment_out_of_range" for i in issues)


class TestUnifiedValidator:
    """Test unified DataValidator interface."""
    
    def test_validate_bars(self, sample_bars):
        """Test bar validation through unified interface."""
        validator = DataValidator()
        issues = validator.validate_bars(sample_bars)
        assert isinstance(issues, list)
    
    def test_validate_ticks(self, sample_ticks):
        """Test tick validation through unified interface."""
        validator = DataValidator()
        issues = validator.validate_ticks(sample_ticks)
        assert isinstance(issues, list)
    
    def test_validate_any(self, sample_bars, sample_ticks, sample_order_book):
        """Test auto-type detection validation."""
        validator = DataValidator()
        
        assert len(validator.validate_any(sample_bars[0])) == 0
        assert len(validator.validate_any(sample_ticks[0])) == 0
        assert len(validator.validate_any(sample_order_book)) == 0


# ─────────────────────────────────────────────────────────────
# STORAGE TESTS
# ─────────────────────────────────────────────────────────────

class TestDataStore:
    """Test partitioned data storage."""
    
    @pytest.mark.asyncio
    async def test_write_and_read_bars(self, temp_data_dir, sample_bars):
        """Test bar storage round-trip."""
        store = DataStore(temp_data_dir)
        
        # Write
        written = await store.write_bars(
            symbol="AAPL",
            timeframe=TimeFrame.M1,
            bars=sample_bars,
        )
        assert written == len(sample_bars)
        
        # Read
        start = sample_bars[0].timestamp
        end = sample_bars[-1].timestamp
        
        read_bars = await store.read_bars(
            symbol="AAPL",
            timeframe=TimeFrame.M1,
            start=start,
            end=end,
        )
        
        assert len(read_bars) == len(sample_bars)
    
    @pytest.mark.asyncio
    async def test_partitioned_storage(self, temp_data_dir):
        """Test that data is stored in correct partitions."""
        store = DataStore(temp_data_dir)
        
        # Check all dataset directories exist
        for dataset_type in store.DATASET_PATHS.keys():
            assert (temp_data_dir / dataset_type).exists()
    
    @pytest.mark.asyncio
    async def test_list_symbols(self, temp_data_dir, sample_bars):
        """Test listing stored symbols."""
        store = DataStore(temp_data_dir)
        
        await store.write_bars("AAPL", TimeFrame.M1, sample_bars)
        await store.write_bars("MSFT", TimeFrame.M1, sample_bars)
        
        symbols = store.list_symbols("bars")
        assert "AAPL" in symbols
        assert "MSFT" in symbols
    
    @pytest.mark.asyncio
    async def test_date_range(self, temp_data_dir, sample_bars):
        """Test getting date range of stored data."""
        store = DataStore(temp_data_dir)
        
        await store.write_bars("AAPL", TimeFrame.M1, sample_bars)
        
        date_range = store.get_date_range("bars", "AAPL", TimeFrame.M1)
        assert date_range is not None
        assert date_range[0] <= date_range[1]


# ─────────────────────────────────────────────────────────────
# REPLAY TESTS
# ─────────────────────────────────────────────────────────────

class TestReplay:
    """Test historical replay functionality."""
    
    @pytest.mark.asyncio
    async def test_replay_config(self):
        """Test replay configuration."""
        config = ReplayConfig(
            symbols=["AAPL"],
            dataset_types=["bars"],
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 2),
            timeframe=TimeFrame.M1,
        )
        
        assert config.symbols == ["AAPL"]
        assert config.dataset_types == ["bars"]
    
    @pytest.mark.asyncio
    async def test_bar_replay_reader(self, temp_data_dir, sample_bars):
        """Test bar replay reader."""
        # First store some data
        store = DataStore(temp_data_dir)
        await store.write_bars("AAPL", TimeFrame.M1, sample_bars)
        
        # Create reader
        reader = BarReplayReader(temp_data_dir, "AAPL", TimeFrame.M1)
        
        # Read slice
        start = sample_bars[0].timestamp
        end = sample_bars[-1].timestamp
        
        bars = reader.read_slice(start, end)
        assert len(bars) == len(sample_bars)
    
    @pytest.mark.asyncio
    async def test_historical_replay(self, temp_data_dir, sample_bars):
        """Test full historical replay."""
        # Store data
        store = DataStore(temp_data_dir)
        await store.write_bars("AAPL", TimeFrame.M1, sample_bars)
        
        # Create replay
        config = ReplayConfig(
            symbols=["AAPL"],
            dataset_types=["bars"],
            start_time=sample_bars[0].timestamp,
            end_time=sample_bars[-1].timestamp,
            slice_interval=timedelta(minutes=5),
            timeframe=TimeFrame.M1,
        )
        
        replay = HistoricalReplay(temp_data_dir, config)
        
        # Iterate
        slices = []
        async for slice_obj in replay.iterate():
            slices.append(slice_obj)
        
        assert len(slices) > 0
        
        # Check progress
        progress = replay.get_progress()
        assert "progress_pct" in progress


# ─────────────────────────────────────────────────────────────
# REGISTRY TESTS
# ─────────────────────────────────────────────────────────────

class TestProviderRegistry:
    """Test provider registry functionality."""
    
    def test_singleton(self):
        """Test registry singleton pattern."""
        reg1 = DataProviderRegistry.get_instance()
        reg2 = DataProviderRegistry.get_instance()
        assert reg1 is reg2
    
    def test_register_and_get(self):
        """Test provider registration and retrieval."""
        registry = DataProviderRegistry()
        
        class MockProvider(MarketDataProvider):
            name = "mock"
            supported_domains = [DataDomain.MARKET_DATA]
            supports_market_data = True
            
            async def connect(self): pass
            async def disconnect(self): pass
            async def is_connected(self): return True
            async def get_bars(self, *args, **kwargs): return []
            async def get_ticks(self, *args, **kwargs): return []
        
        provider = MockProvider()
        registry.register("mock", provider)
        
        retrieved = registry.get("mock")
        assert retrieved is provider
    
    def test_domain_routing(self):
        """Test provider routing by domain."""
        registry = DataProviderRegistry()
        
        class MockProvider(MarketDataProvider):
            name = "mock"
            supported_domains = [DataDomain.MARKET_DATA]
            supports_market_data = True
            
            async def connect(self): pass
            async def disconnect(self): pass
            async def is_connected(self): return True
            async def get_bars(self, *args, **kwargs): return []
        
        provider = MockProvider()
        registry.register("mock", provider)
        
        # Get by domain
        market_providers = registry.list_for_domain(DataDomain.MARKET_DATA)
        assert "mock" in market_providers


# ─────────────────────────────────────────────────────────────
# PROVIDER CONTRACT TESTS
# ─────────────────────────────────────────────────────────────

class TestProviderContracts:
    """Test provider interface contracts."""
    
    @pytest.mark.asyncio
    async def test_market_data_provider_interface(self):
        """Test MarketDataProvider base class."""
        
        class TestProvider(MarketDataProvider):
            name = "test"
            
            async def connect(self):
                self._connected = True
            
            async def disconnect(self):
                self._connected = False
            
            async def is_connected(self):
                return getattr(self, "_connected", False)
            
            async def get_bars(self, symbol, timeframe, start, end):
                return []
            
            async def get_ticks(self, symbol, start, end, limit=10000):
                return []
        
        provider = TestProvider()
        
        # Test domain support
        assert provider.supports_domain(DataDomain.MARKET_DATA)
        assert not provider.supports_domain(DataDomain.FUNDAMENTALS)
        
        # Test connection
        await provider.connect()
        assert await provider.is_connected()
        
        await provider.disconnect()
        assert not await provider.is_connected()
    
    @pytest.mark.asyncio
    async def test_provider_not_implemented(self):
        """Test that unsupported methods raise NotImplementedError."""
        
        class MinimalProvider(DataProvider):
            name = "minimal"
            supported_domains = []
            
            async def connect(self): pass
            async def disconnect(self): pass
            async def is_connected(self): return True
        
        provider = MinimalProvider()
        
        # Should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            await provider.get_bars("AAPL", TimeFrame.M1, datetime.now(), datetime.now())
        
        with pytest.raises(NotImplementedError):
            await provider.get_fundamentals("AAPL")
        
        with pytest.raises(NotImplementedError):
            await provider.get_macro_events("US", datetime.now(), datetime.now())


# ─────────────────────────────────────────────────────────────
# BACKFILL TESTS
# ─────────────────────────────────────────────────────────────

class TestBackfill:
    """Test backfill functionality."""
    
    @pytest.mark.asyncio
    async def test_backfill_manager_creation(self, temp_data_dir):
        """Test backfill manager initialization."""
        from ai_trading_tool.core.data.providers import YahooFinanceProvider
        
        provider = YahooFinanceProvider()
        store = DataStore(temp_data_dir)
        validator = DataValidator()
        
        manager = BackfillManager(provider, store, validator)
        
        assert manager.provider is provider
        assert manager.store is store
        assert manager.validator is validator


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
