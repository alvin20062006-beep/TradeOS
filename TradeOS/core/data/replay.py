"""
Historical Replay - Time-series data replay functionality.

Provides efficient historical data replay with time-sliced iteration,
supporting backtesting and strategy simulation.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator, Callable, Generic, Optional, TypeVar

import pandas as pd
import pyarrow.parquet as pq

from core.data.schemas import (
    MarketBar,
    MarketTick,
    OrderBookSnapshot,
    TradePrint,
    SCHEMA_TYPES,
    TimeFrame,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ReplaySlice:
    """A time slice of replay data."""
    start_time: datetime
    end_time: datetime
    data: list
    symbol: str
    dataset_type: str


@dataclass
class ReplayConfig:
    """Configuration for replay session."""
    symbols: list[str]
    dataset_types: list[str]  # bars, ticks, trades, etc.
    start_time: datetime
    end_time: datetime
    
    # Time slicing
    slice_interval: timedelta = timedelta(minutes=1)
    
    # Playback speed (1.0 = real-time, 0 = as-fast-as-possible)
    playback_speed: float = 0.0
    
    # Buffer settings
    prefetch_slices: int = 5
    
    # Filtering
    timeframe: Optional[TimeFrame] = None  # For bar data
    min_confidence: Optional[float] = None  # For sentiment/news


class ReplayReader(ABC, Generic[T]):
    """
    Abstract base for replay readers.
    
    Each dataset type has its own reader implementation.
    """
    
    def __init__(
        self,
        data_path: Path,
        symbol: str,
        dataset_type: str,
    ):
        self.data_path = data_path
        self.symbol = symbol
        self.dataset_type = dataset_type
        self._current_file: Optional[Path] = None
        self._buffer: list[T] = []
        self._buffer_idx = 0
    
    @abstractmethod
    def _get_file_path(self, timestamp: datetime) -> Path:
        """Get Parquet file path for given timestamp."""
        pass
    
    @abstractmethod
    def _row_to_object(self, row: pd.Series) -> T:
        """Convert DataFrame row to schema object."""
        pass
    
    def _load_file(self, file_path: Path) -> bool:
        """Load Parquet file into buffer."""
        if not file_path.exists():
            return False
        
        try:
            df = pd.read_parquet(file_path)
            self._buffer = [self._row_to_object(row) for _, row in df.iterrows()]
            self._buffer_idx = 0
            self._current_file = file_path
            logger.debug(
                "Loaded replay file",
                file=str(file_path),
                records=len(self._buffer),
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to load replay file",
                file=str(file_path),
                error=str(e),
            )
            return False
    
    def read_slice(
        self,
        start: datetime,
        end: datetime,
    ) -> list[T]:
        """
        Read data for a time slice.
        
        Args:
            start: Slice start time (inclusive)
            end: Slice end time (inclusive)
        
        Returns:
            List of data objects within the time range
        """
        results = []
        
        # Determine which files to read
        current = datetime(start.year, start.month, 1)
        end_month = datetime(end.year, end.month, 1)
        
        while current <= end_month:
            file_path = self._get_file_path(current)
            
            if file_path.exists():
                df = pd.read_parquet(file_path)

                if "timestamp" not in df.columns and (
                    df.index.name == "timestamp" or isinstance(df.index, pd.DatetimeIndex)
                ):
                    df = df.reset_index()
                    if df.columns[0] != "timestamp":
                        df = df.rename(columns={df.columns[0]: "timestamp"})
                
                # Filter by timestamp
                if "timestamp" in df.columns:
                    df = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)]
                
                for _, row in df.iterrows():
                    obj = self._row_to_object(row)
                    results.append(obj)
            
            # Move to next month
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)
        
        return results


class BarReplayReader(ReplayReader[MarketBar]):
    """Replay reader for OHLCV bars."""
    
    def __init__(
        self,
        data_path: Path,
        symbol: str,
        timeframe: TimeFrame,
    ):
        super().__init__(data_path, symbol, "bars")
        self.timeframe = timeframe
    
    def _get_file_path(self, timestamp: datetime) -> Path:
        return (
            self.data_path
            / "bars"
            / self.symbol.upper()
            / self.timeframe.value
            / f"{timestamp.strftime('%Y-%m')}.parquet"
        )
    
    def _row_to_object(self, row: pd.Series) -> MarketBar:
        return MarketBar(
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp=row["timestamp"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            quote_volume=row.get("quote_volume"),
            trades=row.get("trades"),
            vwap=row.get("vwap"),
            source=row.get("source"),
        )


class TickReplayReader(ReplayReader[MarketTick]):
    """Replay reader for tick data."""
    
    def __init__(self, data_path: Path, symbol: str):
        super().__init__(data_path, symbol, "ticks")
    
    def _get_file_path(self, timestamp: datetime) -> Path:
        return (
            self.data_path
            / "ticks"
            / self.symbol.upper()
            / f"{timestamp.strftime('%Y-%m-%d')}.parquet"
        )
    
    def _row_to_object(self, row: pd.Series) -> MarketTick:
        from core.schemas import Side
        return MarketTick(
            symbol=self.symbol,
            timestamp=row["timestamp"],
            price=row["price"],
            size=row["size"],
            side=Side(row["side"]) if pd.notna(row.get("side")) else None,
            bid=row.get("bid"),
            ask=row.get("ask"),
            bid_size=row.get("bid_size"),
            ask_size=row.get("ask_size"),
        )


class TradeReplayReader(ReplayReader[TradePrint]):
    """Replay reader for trade prints."""
    
    def __init__(self, data_path: Path, symbol: str):
        super().__init__(data_path, symbol, "trades")
    
    def _get_file_path(self, timestamp: datetime) -> Path:
        return (
            self.data_path
            / "trades"
            / self.symbol.upper()
            / f"{timestamp.strftime('%Y-%m-%d')}.parquet"
        )
    
    def _row_to_object(self, row: pd.Series) -> TradePrint:
        from core.schemas import Side
        return TradePrint(
            symbol=self.symbol,
            timestamp=row["timestamp"],
            price=row["price"],
            size=row["size"],
            side=Side(row["side"]),
            trade_id=row.get("trade_id"),
            is_buy_side_taker=row.get("is_buy_side_taker"),
        )


class EventReplayReader(ReplayReader):
    """Generic replay reader for event-based data (macro, news, sentiment)."""
    
    def __init__(self, data_path: Path, dataset_type: str):
        super().__init__(data_path, "", dataset_type)
    
    def _get_file_path(self, timestamp: datetime) -> Path:
        return (
            self.data_path
            / self.dataset_type
            / f"{timestamp.strftime('%Y-%m')}.parquet"
        )
    
    def _row_to_object(self, row: pd.Series):
        """Return raw dict for event data."""
        return row.to_dict()


class HistoricalReplay:
    """
    Main replay orchestrator.
    
    Manages multiple readers and provides unified time-sliced iteration.
    """
    
    def __init__(
        self,
        data_path: Path | str,
        config: ReplayConfig,
    ):
        self.data_path = Path(data_path)
        self.config = config
        self._readers: dict[str, ReplayReader] = {}
        self._current_time = config.start_time
        self._is_running = False
        
        self._init_readers()
    
    def _init_readers(self) -> None:
        """Initialize readers for all configured symbols and dataset types."""
        for symbol in self.config.symbols:
            for dataset_type in self.config.dataset_types:
                key = f"{symbol}:{dataset_type}"
                
                if dataset_type == "bars":
                    if self.config.timeframe:
                        self._readers[key] = BarReplayReader(
                            self.data_path,
                            symbol,
                            self.config.timeframe,
                        )
                elif dataset_type == "ticks":
                    self._readers[key] = TickReplayReader(
                        self.data_path,
                        symbol,
                    )
                elif dataset_type == "trades":
                    self._readers[key] = TradeReplayReader(
                        self.data_path,
                        symbol,
                    )
                elif dataset_type in ("macro", "news", "sentiment"):
                    self._readers[key] = EventReplayReader(
                        self.data_path,
                        dataset_type,
                    )
                else:
                    logger.warning(
                        "Unknown dataset type, skipping",
                        dataset_type=dataset_type,
                    )
        
        logger.info(
            "Initialized replay readers",
            readers=len(self._readers),
            symbols=self.config.symbols,
            datasets=self.config.dataset_types,
        )
    
    async def iterate(
        self,
        callback: Optional[Callable[[ReplaySlice], None]] = None,
    ) -> AsyncIterator[ReplaySlice]:
        """
        Iterate through historical data in time slices.
        
        Args:
            callback: Optional callback function called for each slice
        
        Yields:
            ReplaySlice objects in chronological order
        """
        self._is_running = True
        self._current_time = self.config.start_time
        
        while self._is_running and self._current_time < self.config.end_time:
            slice_end = min(
                self._current_time + self.config.slice_interval,
                self.config.end_time,
            )
            
            # Collect data from all readers
            for key, reader in self._readers.items():
                symbol, dataset_type = key.split(":", 1)
                
                data = reader.read_slice(self._current_time, slice_end)
                
                if data:
                    slice_obj = ReplaySlice(
                        start_time=self._current_time,
                        end_time=slice_end,
                        data=data,
                        symbol=symbol,
                        dataset_type=dataset_type,
                    )
                    
                    if callback:
                        callback(slice_obj)
                    
                    yield slice_obj
            
            self._current_time = slice_end
            
            # Simulate real-time playback if configured
            if self.config.playback_speed > 0:
                import asyncio
                sleep_duration = (
                    self.config.slice_interval.total_seconds()
                    / self.config.playback_speed
                )
                await asyncio.sleep(sleep_duration)
    
    def stop(self) -> None:
        """Stop the replay."""
        self._is_running = False
        logger.info("Replay stopped")
    
    def seek(self, timestamp: datetime) -> None:
        """Seek to a specific timestamp."""
        self._current_time = timestamp
        logger.info("Replay seek", timestamp=timestamp.isoformat())
    
    def get_progress(self) -> dict:
        """Get current replay progress."""
        total_duration = self.config.end_time - self.config.start_time
        elapsed = self._current_time - self.config.start_time
        
        return {
            "current_time": self._current_time.isoformat(),
            "start_time": self.config.start_time.isoformat(),
            "end_time": self.config.end_time.isoformat(),
            "progress_pct": (elapsed / total_duration * 100) if total_duration else 0,
            "is_running": self._is_running,
        }


class ReplayDemo:
    """Minimal replay demo for testing."""
    
    @staticmethod
    async def run_demo(
        data_path: Path,
        symbol: str = "AAPL",
        days: int = 1,
    ) -> None:
        """Run a minimal replay demo."""
        from datetime import datetime, timedelta
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        config = ReplayConfig(
            symbols=[symbol],
            dataset_types=["bars"],
            start_time=start_time,
            end_time=end_time,
            slice_interval=timedelta(hours=1),
            timeframe=TimeFrame.M1,
        )
        
        replay = HistoricalReplay(data_path, config)
        
        print(f"Starting replay demo for {symbol}")
        print(f"Time range: {start_time} to {end_time}")
        print("-" * 50)
        
        slice_count = 0
        total_bars = 0
        
        async for slice_obj in replay.iterate():
            slice_count += 1
            total_bars += len(slice_obj.data)
            
            print(
                f"[{slice_obj.start_time}] "
                f"{slice_obj.symbol} {slice_obj.dataset_type}: "
                f"{len(slice_obj.data)} records"
            )
        
        print("-" * 50)
        print(f"Demo complete: {slice_count} slices, {total_bars} total bars")


__all__ = [
    "ReplaySlice",
    "ReplayConfig",
    "ReplayReader",
    "BarReplayReader",
    "TickReplayReader",
    "TradeReplayReader",
    "EventReplayReader",
    "HistoricalReplay",
    "ReplayDemo",
]

