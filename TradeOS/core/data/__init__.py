"""Data layer public exports.

The package exposes the Phase 1 data contracts from one stable import point so
older tests and newer runtime code do not drift across internal module names.
"""

from __future__ import annotations

from .backfill import BackfillManager, BackfillResult
from .base import (
    DataDomain,
    DataProvider,
    FundamentalDataProvider,
    MacroDataProvider,
    MarketDataProvider,
    MultiDomainProvider,
    NewsDataProvider,
    SentimentDataProvider,
    StreamingDataProvider,
)
from .live import LiveAnalysisOrchestrator
from .registry import (
    DataProviderRegistry,
    get_provider,
    get_provider_for_domain,
    register_provider,
)
from .replay import (
    BarReplayReader,
    EventReplayReader,
    HistoricalReplay,
    ReplayConfig,
    ReplayReader,
    ReplaySlice,
    TickReplayReader,
    TradeReplayReader,
)
from .schemas import (
    MARKET_DATA_SCHEMAS,
    RESEARCH_DATA_SCHEMAS,
    SCHEMA_TYPES,
    FundamentalsSnapshot,
    MacroEvent,
    MarketBar,
    MarketTick,
    NewsEvent,
    OrderBookSnapshot,
    SentimentEvent,
    TimeFrame,
    TradePrint,
    get_schema_type,
    list_schema_types,
)
from .source_registry import (
    DataSourceProfile,
    DataSourceRegistry,
    ProviderCapability,
    ProviderCapabilityStatus,
    ProviderTestResult,
)
from .store import DataStore
from .validator import (
    BarValidator,
    DataValidator,
    EventValidator,
    FundamentalsValidator,
    OrderBookValidator,
    TickValidator,
    ValidationIssue,
)

__all__ = [
    "BackfillManager",
    "BackfillResult",
    "BarReplayReader",
    "BarValidator",
    "DataDomain",
    "DataProvider",
    "DataProviderRegistry",
    "DataSourceProfile",
    "DataSourceRegistry",
    "DataStore",
    "DataValidator",
    "EventReplayReader",
    "EventValidator",
    "FundamentalDataProvider",
    "FundamentalsSnapshot",
    "FundamentalsValidator",
    "HistoricalReplay",
    "LiveAnalysisOrchestrator",
    "MARKET_DATA_SCHEMAS",
    "MacroDataProvider",
    "MacroEvent",
    "MarketBar",
    "MarketDataProvider",
    "MarketTick",
    "MultiDomainProvider",
    "NewsDataProvider",
    "NewsEvent",
    "OrderBookSnapshot",
    "OrderBookValidator",
    "ProviderCapability",
    "ProviderCapabilityStatus",
    "ProviderTestResult",
    "RESEARCH_DATA_SCHEMAS",
    "ReplayConfig",
    "ReplayReader",
    "ReplaySlice",
    "SCHEMA_TYPES",
    "SentimentDataProvider",
    "SentimentEvent",
    "StreamingDataProvider",
    "TickReplayReader",
    "TickValidator",
    "TimeFrame",
    "TradePrint",
    "TradeReplayReader",
    "ValidationIssue",
    "get_provider",
    "get_provider_for_domain",
    "get_schema_type",
    "list_schema_types",
    "register_provider",
]
