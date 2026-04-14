"""
Yahoo Finance Data Provider

Provides historical market data using yfinance library.
Supports market data and fundamentals domains.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional, AsyncIterator, TYPE_CHECKING

import yfinance as yf

from ai_trading_tool.core.data.base import (
    DataProvider,
    DataDomain,
    MarketDataProvider,
)
from ai_trading_tool.core.schemas import (
    MarketBar,
    MarketTick,
    TimeFrame,
    FundamentalsSnapshot,
)

if TYPE_CHECKING:
    import pandas as pd


class YahooFinanceProvider(MarketDataProvider):
    """
    Yahoo Finance data provider.
    
    Supports:
    - Historical OHLCV bars (market data domain)
    - Intraday bars (5m, 15m, 1h, etc.)
    - Fundamental data (fundamentals domain)
    """
    
    name = "yfinance"
    supported_domains = [DataDomain.MARKET_DATA, DataDomain.FUNDAMENTALS]
    supports_market_data = True
    supports_fundamentals = True
    supported_timeframes = [
        TimeFrame.M5,
        TimeFrame.M15,
        TimeFrame.M30,
        TimeFrame.H1,
        TimeFrame.H4,
        TimeFrame.D1,
        TimeFrame.W1,
    ]
    
    # yfinance interval mapping
    TIMEFRAME_MAP = {
        TimeFrame.M5: "5m",
        TimeFrame.M15: "15m",
        TimeFrame.M30: "30m",
        TimeFrame.H1: "1h",
        TimeFrame.H4: "4h",
        TimeFrame.D1: "1d",
        TimeFrame.W1: "1wk",
    }
    
    def __init__(
        self,
        cache_ttl_seconds: int = 300,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        super().__init__()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._cache: dict[str, tuple[datetime, pd.DataFrame]] = {}
        self._connected = False
    
    async def connect(self) -> None:
        """Initialize connection (yfinance doesn't require explicit connection)."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Close connection."""
        self._cache.clear()
        self._connected = False
    
    async def is_connected(self) -> bool:
        """Check if provider is connected."""
        return self._connected
    
    # ─────────────────────────────────────────────────────────
    # MARKET DATA
    # ─────────────────────────────────────────────────────────
    
    async def get_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
    ) -> list[MarketBar]:
        """
        Fetch historical OHLCV bars from Yahoo Finance.
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'MSFT')
            timeframe: Bar timeframe
            start: Start datetime
            end: End datetime
        
        Returns:
            List of MarketBar objects
        """
        if timeframe not in self.TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        # Check cache
        cache_key = f"{symbol}_{timeframe}_{start.date()}_{end.date()}"
        if cache_key in self._cache:
            cache_time, cached_df = self._cache[cache_key]
            if (datetime.now() - cache_time).seconds < self.cache_ttl_seconds:
                return self._df_to_bars(cached_df, symbol, timeframe)
        
        # Fetch from Yahoo Finance
        ticker = yf.Ticker(symbol)
        interval = self.TIMEFRAME_MAP[timeframe]
        
        # Calculate period
        period = self._calculate_period(start, end)
        
        # Download with retries
        for attempt in range(self.max_retries):
            try:
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                df = await loop.run_in_executor(
                    None,
                    lambda: ticker.history(
                        start=start,
                        end=end,
                        interval=interval,
                    )
                )
                
                if df.empty:
                    return []
                
                # Cache result
                self._cache[cache_key] = (datetime.now(), df)
                
                return self._df_to_bars(df, symbol, timeframe)
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
        
        return []
    
    async def get_fundamentals(
        self,
        symbol: str,
    ) -> Optional[FundamentalsSnapshot]:
        """
        Get fundamental data for symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            FundamentalsSnapshot or None if not available
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Run in thread pool
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                lambda: ticker.info
            )
            
            if not info:
                return None
            
            return FundamentalsSnapshot(
                symbol=symbol,
                timestamp=datetime.now(),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                pb_ratio=info.get("priceToBook"),
                ps_ratio=info.get("priceToSalesTrailing12Months"),
                peg_ratio=info.get("pegRatio"),
                revenue=info.get("totalRevenue"),
                ebitda=info.get("ebitda"),
                net_income=info.get("netIncomeToCommon"),
                total_assets=info.get("totalAssets"),
                total_debt=info.get("totalDebt"),
                eps=info.get("trailingEps"),
                book_value_per_share=info.get("bookValue"),
                dividend_yield=info.get("dividendYield"),
                beta=info.get("beta"),
                avg_volume_20d=info.get("averageVolume"),
            )
            
        except Exception as e:
            return None
    
    async def get_symbols(self) -> list[str]:
        """Get list of available symbols (not supported by yfinance)."""
        return []
    
    async def get_trading_hours(self, symbol: str) -> dict:
        """Get trading hours for symbol."""
        try:
            ticker = yf.Ticker(symbol)
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: ticker.info)
            
            return {
                "timezone": info.get("timeZoneFullName"),
                "market_open": info.get("regularMarketOpen"),
                "market_close": info.get("regularMarketPreviousClose"),
            }
        except:
            return {}
    
    def _df_to_bars(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: TimeFrame,
    ) -> list[MarketBar]:
        """Convert DataFrame to list of MarketBar."""
        bars = []
        
        for timestamp, row in df.iterrows():
            # Handle timezone
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=datetime.now().astimezone().tzinfo)
            
            bar = MarketBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
                quote_volume=None,
                trades=None,
                vwap=None,
                source="yfinance",
            )
            bars.append(bar)
        
        return bars
    
    def _calculate_period(self, start: datetime, end: datetime) -> str:
        """Calculate appropriate period string for yfinance."""
        delta = end - start
        
        if delta.days <= 7:
            return "7d"
        elif delta.days <= 30:
            return "1mo"
        elif delta.days <= 90:
            return "3mo"
        elif delta.days <= 180:
            return "6mo"
        elif delta.days <= 365:
            return "1y"
        elif delta.days <= 730:
            return "2y"
        elif delta.days <= 1825:
            return "5y"
        else:
            return "max"


__all__ = ["YahooFinanceProvider"]
