"""
Data Provider Base - Abstract interface for all data providers.

Supports multiple data domains:
- market_data: OHLCV bars, ticks, order books, trades
- fundamentals: Financial statements, ratios
- macro: Economic indicators, calendar events
- news: News headlines, articles
- sentiment: Aggregated sentiment signals
- local_file: CSV, Parquet files
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional, AsyncIterator

from core.schemas import (
    MarketBar,
    MarketTick,
    OrderBookSnapshot,
    TradePrint,
    FundamentalsSnapshot,
    MacroEvent,
    NewsEvent,
    SentimentEvent,
    TimeFrame,
)


class DataDomain(str, Enum):
    """Data domain categories."""
    MARKET_DATA = "market_data"
    FUNDAMENTALS = "fundamentals"
    MACRO = "macro"
    NEWS = "news"
    SENTIMENT = "sentiment"
    LOCAL_FILE = "local_file"


class DataProvider(ABC):
    """
    Abstract base class for all data providers.
    
    All data providers must implement this interface.
    Providers can support multiple data domains.
    """
    
    name: str
    supported_domains: list[DataDomain] = []
    supported_symbols: Optional[list[str]] = None
    supported_timeframes: list[TimeFrame] = []
    
    # Domain capability flags
    supports_market_data: bool = False
    supports_fundamentals: bool = False
    supports_macro: bool = False
    supports_news: bool = False
    supports_sentiment: bool = False
    supports_local_file: bool = False
    
    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to data source."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to data source."""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if provider is connected."""
        pass
    
    def supports_domain(self, domain: DataDomain) -> bool:
        """Check if provider supports a specific data domain."""
        return domain in self.supported_domains
    
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # MARKET DATA DOMAIN
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    
    async def get_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
    ) -> list[MarketBar]:
        """
        Fetch historical OHLCV bars.
        
        Override if supports_market_data=True.
        
        Args:
            symbol: Trading symbol
            timeframe: Bar timeframe
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
        
        Returns:
            List of MarketBar objects
        
        Raises:
            NotImplementedError: If market data not supported
        """
        raise NotImplementedError(
            f"{self.name} does not support market data (bars)"
        )
    
    async def get_ticks(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        limit: int = 10000,
    ) -> list[MarketTick]:
        """
        Fetch historical tick data.
        
        Override if supports_market_data=True.
        """
        raise NotImplementedError(
            f"{self.name} does not support market data (ticks)"
        )
    
    async def get_order_book(
        self,
        symbol: str,
        depth: int = 10,
    ) -> Optional[OrderBookSnapshot]:
        """
        Get current order book snapshot.
        
        Override if supports_market_data=True.
        """
        raise NotImplementedError(
            f"{self.name} does not support market data (order book)"
        )
    
    async def get_trades(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        limit: int = 10000,
    ) -> list[TradePrint]:
        """
        Fetch historical trade prints.
        
        Override if supports_market_data=True.
        """
        raise NotImplementedError(
            f"{self.name} does not support market data (trades)"
        )
    
    async def subscribe_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
    ) -> AsyncIterator[MarketBar]:
        """
        Subscribe to real-time bar updates.
        
        Override if supports_market_data=True and streaming supported.
        """
        raise NotImplementedError(
            f"{self.name} does not support real-time market data"
        )
    
    async def subscribe_ticks(
        self,
        symbol: str,
    ) -> AsyncIterator[MarketTick]:
        """
        Subscribe to real-time tick updates.
        
        Override if supports_market_data=True and streaming supported.
        """
        raise NotImplementedError(
            f"{self.name} does not support real-time market data"
        )
    
    async def subscribe_order_book(
        self,
        symbol: str,
    ) -> AsyncIterator[OrderBookSnapshot]:
        """
        Subscribe to real-time order book updates.
        
        Override if supports_market_data=True and streaming supported.
        """
        raise NotImplementedError(
            f"{self.name} does not support real-time market data"
        )
    
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # FUNDAMENTALS DOMAIN
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    
    async def get_fundamentals(
        self,
        symbol: str,
    ) -> Optional[FundamentalsSnapshot]:
        """
        Get fundamental data for symbol.
        
        Override if supports_fundamentals=True.
        """
        raise NotImplementedError(
            f"{self.name} does not support fundamentals data"
        )
    
    async def get_fundamentals_history(
        self,
        symbol: str,
        metric: str,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """
        Get historical fundamental metrics.
        
        Override if supports_fundamentals=True.
        """
        raise NotImplementedError(
            f"{self.name} does not support fundamentals history"
        )
    
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # MACRO DOMAIN
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    
    async def get_macro_events(
        self,
        country: str,
        start: datetime,
        end: datetime,
        impact: Optional[str] = None,
    ) -> list[MacroEvent]:
        """
        Get macroeconomic calendar events.
        
        Override if supports_macro=True.
        
        Args:
            country: Country code (e.g., 'US', 'CN')
            start: Start datetime
            end: End datetime
            impact: Filter by impact level (high/medium/low)
        """
        raise NotImplementedError(
            f"{self.name} does not support macro data"
        )
    
    async def get_economic_indicator(
        self,
        indicator: str,
        country: str,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """
        Get specific economic indicator time series.
        
        Override if supports_macro=True.
        
        Args:
            indicator: Indicator name (e.g., 'GDP', 'CPI', 'Unemployment')
            country: Country code
            start: Start datetime
            end: End datetime
        """
        raise NotImplementedError(
            f"{self.name} does not support macro indicators"
        )
    
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # NEWS DOMAIN
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    
    async def get_news(
        self,
        symbols: Optional[list[str]] = None,
        sources: Optional[list[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[NewsEvent]:
        """
        Get news headlines.
        
        Override if supports_news=True.
        
        Args:
            symbols: Filter by related symbols
            sources: Filter by news sources
            start: Start datetime
            end: End datetime
            limit: Maximum results
        """
        raise NotImplementedError(
            f"{self.name} does not support news data"
        )
    
    async def search_news(
        self,
        query: str,
        symbols: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[NewsEvent]:
        """
        Search news by keyword.
        
        Override if supports_news=True.
        """
        raise NotImplementedError(
            f"{self.name} does not support news search"
        )
    
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # SENTIMENT DOMAIN
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    
    async def get_sentiment(
        self,
        symbol: str,
        sources: Optional[list[str]] = None,
    ) -> Optional[SentimentEvent]:
        """
        Get aggregated sentiment for symbol.
        
        Override if supports_sentiment=True.
        
        Args:
            symbol: Trading symbol
            sources: Sentiment sources (news, social, forum, analyst)
        """
        raise NotImplementedError(
            f"{self.name} does not support sentiment data"
        )
    
    async def get_sentiment_history(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        granularity: str = "1h",
    ) -> list[SentimentEvent]:
        """
        Get historical sentiment time series.
        
        Override if supports_sentiment=True.
        """
        raise NotImplementedError(
            f"{self.name} does not support sentiment history"
        )
    
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # REFERENCE DATA
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    
    async def get_symbols(self) -> list[str]:
        """Get list of available symbols."""
        return []
    
    async def get_symbol_info(self, symbol: str) -> dict:
        """Get detailed symbol information."""
        return {}
    
    async def get_trading_hours(self, symbol: str) -> dict:
        """Get trading hours for symbol."""
        return {}
    
    async def get_available_metrics(self, symbol: str) -> list[str]:
        """Get list of available fundamental/macro metrics."""
        return []


class MarketDataProvider(DataProvider):
    """
    Base class for market data providers.
    
    Implements common market data functionality.
    """
    
    supported_domains = [DataDomain.MARKET_DATA]
    supports_market_data = True
    
    def __init__(self):
        self._streaming = False
        self._subscriptions: dict[str, any] = {}


class FundamentalDataProvider(DataProvider):
    """Base class for fundamental data providers."""
    
    supported_domains = [DataDomain.FUNDAMENTALS]
    supports_fundamentals = True


class MacroDataProvider(DataProvider):
    """Base class for macroeconomic data providers."""
    
    supported_domains = [DataDomain.MACRO]
    supports_macro = True


class NewsDataProvider(DataProvider):
    """Base class for news data providers."""
    
    supported_domains = [DataDomain.NEWS]
    supports_news = True


class SentimentDataProvider(DataProvider):
    """Base class for sentiment data providers."""
    
    supported_domains = [DataDomain.SENTIMENT]
    supports_sentiment = True


class MultiDomainProvider(DataProvider):
    """
    Base class for providers supporting multiple domains.
    
    Example: A provider that offers both market data and news.
    """
    
    supported_domains: list[DataDomain] = []
    
    def __init__(self):
        self._domain_capabilities: dict[DataDomain, bool] = {}
    
    def register_domain(
        self,
        domain: DataDomain,
        supported: bool = True,
    ) -> None:
        """Register support for a data domain."""
        self._domain_capabilities[domain] = supported
        if supported and domain not in self.supported_domains:
            self.supported_domains.append(domain)


class StreamingDataProvider(DataProvider):
    """
    Mixin for providers that support real-time streaming.
    """
    
    supports_streaming: bool = True
    
    async def unsubscribe(self, symbol: str) -> None:
        """Unsubscribe from all streams for symbol."""
        pass
    
    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all streams."""
        pass


__all__ = [
    "DataDomain",
    "DataProvider",
    "MarketDataProvider",
    "FundamentalDataProvider",
    "MacroDataProvider",
    "NewsDataProvider",
    "SentimentDataProvider",
    "MultiDomainProvider",
    "StreamingDataProvider",
]

