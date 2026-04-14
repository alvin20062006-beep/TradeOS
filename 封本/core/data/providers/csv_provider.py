"""
CSV Data Provider

Provides historical market data from local CSV files.
Supports market data domain with local file storage.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ai_trading_tool.core.data.base import (
    DataProvider,
    DataDomain,
    MarketDataProvider,
)
from ai_trading_tool.core.schemas import (
    MarketBar,
    TimeFrame,
)


class CSVProvider(MarketDataProvider):
    """
    CSV file data provider.
    
    Reads OHLCV data from local CSV files.
    Supports standard CSV formats with columns:
    - timestamp, open, high, low, close, volume
    - or: date, open, high, low, close, volume
    """
    
    name = "csv"
    supported_domains = [DataDomain.MARKET_DATA, DataDomain.LOCAL_FILE]
    supports_market_data = True
    supports_local_file = True
    supported_timeframes = [
        TimeFrame.M1,
        TimeFrame.M5,
        TimeFrame.M15,
        TimeFrame.M30,
        TimeFrame.H1,
        TimeFrame.H4,
        TimeFrame.D1,
    ]
    
    # Expected column mappings
    COLUMN_MAPPINGS = {
        "timestamp": ["timestamp", "datetime", "date", "time", "ts"],
        "open": ["open", "o"],
        "high": ["high", "h"],
        "low": ["low", "l"],
        "close": ["close", "c"],
        "volume": ["volume", "vol", "v"],
    }
    
    def __init__(
        self,
        data_dir: str | Path,
        default_timeframe: TimeFrame = TimeFrame.D1,
    ):
        super().__init__()
        self.data_dir = Path(data_dir)
        self.default_timeframe = default_timeframe
        self._connected = False
        self._file_cache: dict[str, pd.DataFrame] = {}
    
    async def connect(self) -> None:
        """Initialize connection - validate data directory exists."""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        self._connected = True
    
    async def disconnect(self) -> None:
        """Close connection."""
        self._file_cache.clear()
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
        Fetch historical bars from CSV file.
        
        Args:
            symbol: Symbol name (used as filename without extension)
            timeframe: Bar timeframe (used to locate file)
            start: Start datetime
            end: End datetime
        
        Returns:
            List of MarketBar objects
        """
        # Look for file: {data_dir}/{symbol}_{timeframe}.csv or {data_dir}/{symbol}.csv
        file_paths = [
            self.data_dir / f"{symbol}_{timeframe.value}.csv",
            self.data_dir / f"{symbol.upper()}_{timeframe.value}.csv",
            self.data_dir / f"{symbol}.csv",
            self.data_dir / f"{symbol.upper()}.csv",
        ]
        
        file_path = None
        for fp in file_paths:
            if fp.exists():
                file_path = fp
                break
        
        if file_path is None:
            raise FileNotFoundError(
                f"No CSV file found for {symbol} with timeframe {timeframe.value}"
            )
        
        # Load and cache
        cache_key = str(file_path)
        if cache_key in self._file_cache:
            df = self._file_cache[cache_key]
        else:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: pd.read_csv(file_path)
            )
            self._file_cache[cache_key] = df
        
        # Standardize columns
        df = self._standardize_columns(df)
        
        # Parse timestamps
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # Filter by date range
        df = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)]
        
        # Convert to MarketBar
        return self._df_to_bars(df, symbol, timeframe)
    
    async def load_csv(
        self,
        file_path: str | Path,
        symbol: str,
        timeframe: Optional[TimeFrame] = None,
    ) -> list[MarketBar]:
        """
        Load bars directly from a CSV file.
        
        Args:
            file_path: Path to CSV file
            symbol: Symbol to assign to data
            timeframe: Timeframe of data (defaults to provider default)
        
        Returns:
            List of MarketBar objects
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: pd.read_csv(file_path)
        )
        
        df = self._standardize_columns(df)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        tf = timeframe or self.default_timeframe
        return self._df_to_bars(df, symbol, tf)
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names to expected format."""
        df = df.copy()
        
        # Convert column names to lowercase
        df.columns = [col.lower().strip() for col in df.columns]
        
        # Map columns
        column_map = {}
        for standard, alternatives in self.COLUMN_MAPPINGS.items():
            for alt in alternatives:
                if alt in df.columns:
                    column_map[alt] = standard
                    break
        
        df = df.rename(columns=column_map)
        
        # Validate required columns
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        return df
    
    def _df_to_bars(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: TimeFrame,
    ) -> list[MarketBar]:
        """Convert DataFrame to list of MarketBar."""
        bars = []
        
        for _, row in df.iterrows():
            timestamp = row["timestamp"]
            if isinstance(timestamp, pd.Timestamp):
                timestamp = timestamp.to_pydatetime()
            
            bar = MarketBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                quote_volume=row.get("quote_volume"),
                trades=row.get("trades"),
                vwap=row.get("vwap"),
                source="csv",
            )
            bars.append(bar)
        
        return bars
    
    async def get_symbols(self) -> list[str]:
        """Get list of available symbols from CSV files."""
        symbols = []
        
        for file_path in self.data_dir.glob("*.csv"):
            # Extract symbol from filename
            name = file_path.stem
            # Remove timeframe suffix if present
            for tf in self.supported_timeframes:
                if name.endswith(f"_{tf.value}"):
                    name = name[:-len(f"_{tf.value}")]
                    break
            symbols.append(name)
        
        return sorted(set(symbols))


__all__ = ["CSVProvider"]
