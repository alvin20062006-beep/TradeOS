"""
Data Store - Persistent storage for all data types.

Supports partitioned storage by dataset_type:
- bars/     - OHLCV market data
- ticks/    - Tick-level market data
- orderbooks/ - Order book snapshots
- trades/   - Trade prints
- fundamentals/ - Fundamental data
- macro/    - Macroeconomic events
- news/     - News headlines
- sentiment/ - Sentiment signals

Uses Parquet for efficient columnar storage.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ai_trading_tool.core.data.schemas import (
    MarketBar,
    MarketTick,
    OrderBookSnapshot,
    TradePrint,
    FundamentalsSnapshot,
    MacroEvent,
    NewsEvent,
    SentimentEvent,
    SCHEMA_TYPES,
    TimeFrame,
    get_schema_type,
)

logger = logging.getLogger(__name__)


class DataStore:
    """
    Partitioned data storage by dataset type.
    
    Directory structure:
        {data_path}/
            bars/{symbol}/{timeframe}/YYYY-MM.parquet
            ticks/{symbol}/YYYY-MM-DD.parquet
            orderbooks/{symbol}/YYYY-MM-DD.parquet
            trades/{symbol}/YYYY-MM-DD.parquet
            fundamentals/{symbol}/YYYY-MM.parquet
            macro/YYYY-MM.parquet
            news/YYYY-MM-DD.parquet
            sentiment/{symbol}/YYYY-MM-DD.parquet
    """
    
    # Dataset type to subfolder mapping
    DATASET_PATHS = {
        "bars": "bars",
        "ticks": "ticks",
        "orderbooks": "orderbooks",
        "trades": "trades",
        "fundamentals": "fundamentals",
        "macro": "macro",
        "news": "news",
        "sentiment": "sentiment",
    }
    
    def __init__(
        self,
        data_path: Path | str,
        compression: str = "snappy",
    ):
        self.data_path = Path(data_path)
        self.compression = compression
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Create all dataset directories
        for dataset_type in self.DATASET_PATHS.values():
            (self.data_path / dataset_type).mkdir(exist_ok=True)
    
    def _get_partition_path(
        self,
        dataset_type: str,
        symbol: Optional[str] = None,
        timeframe: Optional[TimeFrame] = None,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """
        Get storage path for a dataset partition.
        
        Args:
            dataset_type: Type of data (bars, ticks, etc.)
            symbol: Trading symbol (if applicable)
            timeframe: Bar timeframe (for bars only)
            timestamp: Data timestamp for partitioning
        """
        base_path = self.data_path / self.DATASET_PATHS.get(dataset_type, dataset_type)
        
        if symbol:
            base_path = base_path / symbol.upper()
        
        if timeframe and dataset_type == "bars":
            base_path = base_path / timeframe.value
        
        return base_path
    
    def _get_file_path(
        self,
        dataset_type: str,
        symbol: Optional[str] = None,
        timeframe: Optional[TimeFrame] = None,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """Get full file path for data storage."""
        partition_path = self._get_partition_path(
            dataset_type, symbol, timeframe, timestamp
        )
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Different partition strategies by dataset type
        if dataset_type in ("ticks", "trades", "orderbooks", "news", "sentiment"):
            # Daily partitioning for high-frequency/event data
            filename = f"{timestamp.strftime('%Y-%m-%d')}.parquet"
        else:
            # Monthly partitioning for aggregated data
            filename = f"{timestamp.strftime('%Y-%m')}.parquet"
        
        return partition_path / filename
    
    # ─────────────────────────────────────────────────────────
    # BARS (OHLCV)
    # ─────────────────────────────────────────────────────────
    
    async def write_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        bars: list[MarketBar],
    ) -> int:
        """Write OHLCV bars to storage."""
        if not bars:
            return 0
        
        # Group bars by month
        by_month: dict[datetime, list[dict]] = {}
        for bar in bars:
            month_key = datetime(bar.timestamp.year, bar.timestamp.month, 1)
            if month_key not in by_month:
                by_month[month_key] = []
            
            by_month[month_key].append({
                "timestamp": bar.timestamp,
                "symbol": bar.symbol,
                "timeframe": bar.timeframe.value,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "quote_volume": bar.quote_volume,
                "trades": bar.trades,
                "vwap": bar.vwap,
                "source": bar.source,
            })
        
        total_written = 0
        
        for month_date, records in by_month.items():
            file_path = self._get_file_path(
                "bars", symbol, timeframe, month_date
            )
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            total_written += self._write_partition(file_path, records)
        
        logger.info(
            "Wrote bars to storage",
            symbol=symbol,
            timeframe=timeframe.value,
            count=total_written,
        )
        
        return total_written
    
    async def read_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
    ) -> list[MarketBar]:
        """Read OHLCV bars from storage."""
        bars = []
        
        current = datetime(start.year, start.month, 1)
        end_month = datetime(end.year, end.month, 1)
        
        while current <= end_month:
            file_path = self._get_file_path("bars", symbol, timeframe, current)
            
            if file_path.exists():
                df = pd.read_parquet(file_path)
                df = df[(df.index >= start) & (df.index <= end)]
                
                for idx, row in df.iterrows():
                    bars.append(MarketBar(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=idx,
                        open=row["open"],
                        high=row["high"],
                        low=row["low"],
                        close=row["close"],
                        volume=row["volume"],
                        quote_volume=row.get("quote_volume"),
                        trades=row.get("trades"),
                        vwap=row.get("vwap"),
                        source=row.get("source"),
                    ))
            
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)
        
        return bars
    
    # ─────────────────────────────────────────────────────────
    # TICKS
    # ─────────────────────────────────────────────────────────
    
    async def write_ticks(
        self,
        symbol: str,
        ticks: list[MarketTick],
    ) -> int:
        """Write tick data to storage."""
        if not ticks:
            return 0
        
        # Group by day
        by_day: dict[datetime, list[dict]] = {}
        for tick in ticks:
            day_key = datetime(tick.timestamp.year, tick.timestamp.month, tick.timestamp.day)
            if day_key not in by_day:
                by_day[day_key] = []
            
            by_day[day_key].append({
                "timestamp": tick.timestamp,
                "symbol": tick.symbol,
                "price": tick.price,
                "size": tick.size,
                "side": tick.side.value if tick.side else None,
                "bid": tick.bid,
                "ask": tick.ask,
                "bid_size": tick.bid_size,
                "ask_size": tick.ask_size,
            })
        
        total_written = 0
        for day_date, records in by_day.items():
            file_path = self._get_file_path("ticks", symbol, timestamp=day_date)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            total_written += self._write_partition(file_path, records)
        
        return total_written
    
    async def read_ticks(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[MarketTick]:
        """Read tick data from storage."""
        ticks = []
        
        current = datetime(start.year, start.month, start.day)
        end_day = datetime(end.year, end.month, end.day)
        
        while current <= end_day:
            file_path = self._get_file_path("ticks", symbol, timestamp=current)
            
            if file_path.exists():
                df = pd.read_parquet(file_path)
                df = df[(df.index >= start) & (df.index <= end)]
                
                for idx, row in df.iterrows():
                    from ai_trading_tool.core.schemas import Side
                    ticks.append(MarketTick(
                        symbol=symbol,
                        timestamp=idx,
                        price=row["price"],
                        size=row["size"],
                        side=Side(row["side"]) if pd.notna(row.get("side")) else None,
                        bid=row.get("bid"),
                        ask=row.get("ask"),
                        bid_size=row.get("bid_size"),
                        ask_size=row.get("ask_size"),
                    ))
            
            current += timedelta(days=1)
        
        return ticks
    
    # ─────────────────────────────────────────────────────────
    # ORDER BOOKS
    # ─────────────────────────────────────────────────────────
    
    async def write_order_books(
        self,
        symbol: str,
        snapshots: list[OrderBookSnapshot],
    ) -> int:
        """Write order book snapshots to storage."""
        if not snapshots:
            return 0
        
        # Group by day
        by_day: dict[datetime, list[dict]] = {}
        for snap in snapshots:
            day_key = datetime(snap.timestamp.year, snap.timestamp.month, snap.timestamp.day)
            if day_key not in by_day:
                by_day[day_key] = []
            
            by_day[day_key].append({
                "timestamp": snap.timestamp,
                "symbol": snap.symbol,
                "bids": snap.bids,
                "asks": snap.asks,
                "bid_depth": snap.bid_depth,
                "ask_depth": snap.ask_depth,
                "spread": snap.spread,
                "mid_price": snap.mid_price,
                "imbalance": snap.imbalance,
            })
        
        total_written = 0
        for day_date, records in by_day.items():
            file_path = self._get_file_path("orderbooks", symbol, timestamp=day_date)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            total_written += self._write_partition(file_path, records)
        
        return total_written
    
    # ─────────────────────────────────────────────────────────
    # TRADES
    # ─────────────────────────────────────────────────────────
    
    async def write_trades(
        self,
        symbol: str,
        trades: list[TradePrint],
    ) -> int:
        """Write trade prints to storage."""
        if not trades:
            return 0
        
        by_day: dict[datetime, list[dict]] = {}
        for trade in trades:
            day_key = datetime(trade.timestamp.year, trade.timestamp.month, trade.timestamp.day)
            if day_key not in by_day:
                by_day[day_key] = []
            
            by_day[day_key].append({
                "timestamp": trade.timestamp,
                "symbol": trade.symbol,
                "price": trade.price,
                "size": trade.size,
                "side": trade.side.value,
                "trade_id": trade.trade_id,
                "is_buy_side_taker": trade.is_buy_side_taker,
            })
        
        total_written = 0
        for day_date, records in by_day.items():
            file_path = self._get_file_path("trades", symbol, timestamp=day_date)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            total_written += self._write_partition(file_path, records)
        
        return total_written
    
    # ─────────────────────────────────────────────────────────
    # FUNDAMENTALS
    # ─────────────────────────────────────────────────────────
    
    async def write_fundamentals(
        self,
        symbol: str,
        snapshot: FundamentalsSnapshot,
    ) -> int:
        """Write fundamentals snapshot to storage."""
        file_path = self._get_file_path(
            "fundamentals",
            symbol,
            timestamp=snapshot.timestamp,
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        record = {
            "timestamp": snapshot.timestamp,
            "symbol": snapshot.symbol,
            "market_cap": snapshot.market_cap,
            "pe_ratio": snapshot.pe_ratio,
            "pb_ratio": snapshot.pb_ratio,
            "ps_ratio": snapshot.ps_ratio,
            "peg_ratio": snapshot.peg_ratio,
            "revenue": snapshot.revenue,
            "ebitda": snapshot.ebitda,
            "net_income": snapshot.net_income,
            "total_assets": snapshot.total_assets,
            "total_debt": snapshot.total_debt,
            "eps": snapshot.eps,
            "book_value_per_share": snapshot.book_value_per_share,
            "dividend_yield": snapshot.dividend_yield,
            "beta": snapshot.beta,
            "avg_volume_20d": snapshot.avg_volume_20d,
        }
        
        return self._write_partition(file_path, [record])
    
    # ─────────────────────────────────────────────────────────
    # MACRO
    # ─────────────────────────────────────────────────────────
    
    async def write_macro_events(
        self,
        events: list[MacroEvent],
    ) -> int:
        """Write macro events to storage."""
        if not events:
            return 0
        
        # Group by month
        by_month: dict[datetime, list[dict]] = {}
        for event in events:
            month_key = datetime(event.timestamp.year, event.timestamp.month, 1)
            if month_key not in by_month:
                by_month[month_key] = []
            
            by_month[month_key].append({
                "timestamp": event.timestamp,
                "event_name": event.event_name,
                "country": event.country,
                "impact": event.impact,
                "previous": event.previous,
                "forecast": event.forecast,
                "actual": event.actual,
                "affected_assets": event.affected_assets,
                "is_surprise": event.is_surprise,
            })
        
        total_written = 0
        for month_date, records in by_month.items():
            file_path = self._get_file_path("macro", timestamp=month_date)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            total_written += self._write_partition(file_path, records)
        
        return total_written
    
    # ─────────────────────────────────────────────────────────
    # NEWS
    # ─────────────────────────────────────────────────────────
    
    async def write_news(
        self,
        news_items: list[NewsEvent],
    ) -> int:
        """Write news events to storage."""
        if not news_items:
            return 0
        
        # Group by day
        by_day: dict[datetime, list[dict]] = {}
        for item in news_items:
            day_key = datetime(item.timestamp.year, item.timestamp.month, item.timestamp.day)
            if day_key not in by_day:
                by_day[day_key] = []
            
            by_day[day_key].append({
                "timestamp": item.timestamp,
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "symbols": item.symbols,
                "sentiment_score": item.sentiment_score,
                "sentiment_label": item.sentiment_label,
            })
        
        total_written = 0
        for day_date, records in by_day.items():
            file_path = self._get_file_path("news", timestamp=day_date)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            total_written += self._write_partition(file_path, records)
        
        return total_written
    
    # ─────────────────────────────────────────────────────────
    # SENTIMENT
    # ─────────────────────────────────────────────────────────
    
    async def write_sentiment(
        self,
        symbol: str,
        events: list[SentimentEvent],
    ) -> int:
        """Write sentiment events to storage."""
        if not events:
            return 0
        
        # Group by day
        by_day: dict[datetime, list[dict]] = {}
        for event in events:
            day_key = datetime(event.timestamp.year, event.timestamp.month, event.timestamp.day)
            if day_key not in by_day:
                by_day[day_key] = []
            
            by_day[day_key].append({
                "timestamp": event.timestamp,
                "symbol": event.symbol,
                "news_sentiment": event.news_sentiment,
                "social_sentiment": event.social_sentiment,
                "forum_sentiment": event.forum_sentiment,
                "analyst_sentiment": event.analyst_sentiment,
                "composite_sentiment": event.composite_sentiment,
                "bullish_ratio": event.bullish_ratio,
                "bearish_ratio": event.bearish_ratio,
                "neutral_ratio": event.neutral_ratio,
                "sources_count": event.sources_count,
            })
        
        total_written = 0
        for day_date, records in by_day.items():
            file_path = self._get_file_path("sentiment", symbol, timestamp=day_date)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            total_written += self._write_partition(file_path, records)
        
        return total_written
    
    # ─────────────────────────────────────────────────────────
    # GENERIC READ/WRITE
    # ─────────────────────────────────────────────────────────
    
    def _write_partition(
        self,
        file_path: Path,
        records: list[dict],
    ) -> int:
        """
        Write records to a partition file.
        
        Handles merging with existing data.
        """
        if not records:
            return 0
        
        # Read existing data if any
        existing_df = None
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
        
        # Create new DataFrame
        new_df = pd.DataFrame(records)
        if "timestamp" in new_df.columns:
            new_df = new_df.set_index("timestamp")
        
        # Merge
        if existing_df is not None:
            combined_df = pd.concat([existing_df, new_df])
            combined_df = combined_df[~combined_df.index.duplicated(keep="first")]
            combined_df = combined_df.sort_index()
        else:
            combined_df = new_df
        
        # Write
        combined_df.to_parquet(
            file_path,
            compression=self.compression,
            engine="pyarrow",
        )
        
        return len(records)
    
    async def read_dataset(
        self,
        dataset_type: str,
        symbol: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        **filters,
    ) -> pd.DataFrame:
        """
        Generic dataset reader.
        
        Args:
            dataset_type: Type of dataset to read
            symbol: Symbol filter
            start: Start timestamp
            end: End timestamp
            **filters: Additional column filters
        
        Returns:
            DataFrame with requested data
        """
        partition_path = self._get_partition_path(dataset_type, symbol)
        
        if not partition_path.exists():
            return pd.DataFrame()
        
        # Collect all relevant files
        files = list(partition_path.rglob("*.parquet"))
        
        if not files:
            return pd.DataFrame()
        
        # Read and concatenate
        dfs = []
        for file_path in files:
            try:
                df = pd.read_parquet(file_path)
                dfs.append(df)
            except Exception as e:
                logger.warning(
                    "Failed to read file",
                    file=str(file_path),
                    error=str(e),
                )
        
        if not dfs:
            return pd.DataFrame()
        
        result = pd.concat(dfs, ignore_index=True)
        
        # Apply filters
        if "timestamp" in result.columns:
            if start:
                result = result[result["timestamp"] >= start]
            if end:
                result = result[result["timestamp"] <= end]
        
        for key, value in filters.items():
            if key in result.columns:
                result = result[result[key] == value]
        
        return result
    
    # ─────────────────────────────────────────────────────────
    # METADATA
    # ─────────────────────────────────────────────────────────
    
    def list_symbols(self, dataset_type: Optional[str] = None) -> list[str]:
        """List all stored symbols for a dataset type."""
        if dataset_type:
            dataset_path = self.data_path / self.DATASET_PATHS.get(dataset_type, dataset_type)
            if not dataset_path.exists():
                return []
            return sorted([d.name for d in dataset_path.iterdir() if d.is_dir()])
        
        # Return all symbols across all types
        symbols = set()
        for dataset_type in self.DATASET_PATHS.keys():
            symbols.update(self.list_symbols(dataset_type))
        return sorted(list(symbols))
    
    def list_datasets(self) -> list[str]:
        """List all available dataset types."""
        return list(self.DATASET_PATHS.keys())
    
    def get_date_range(
        self,
        dataset_type: str,
        symbol: Optional[str] = None,
        timeframe: Optional[TimeFrame] = None,
    ) -> tuple[datetime, datetime] | None:
        """Get the date range of stored data."""
        partition_path = self._get_partition_path(dataset_type, symbol, timeframe)
        if not partition_path.exists():
            return None
        
        files = sorted(partition_path.rglob("*.parquet"))
        if not files:
            return None
        
        # Read first and last file
        try:
            first_df = pd.read_parquet(files[0])
            last_df = pd.read_parquet(files[-1])
            
            if "timestamp" in first_df.columns:
                return (first_df["timestamp"].min(), last_df["timestamp"].max())
            elif first_df.index.name == "timestamp":
                return (first_df.index.min(), last_df.index.max())
        except Exception as e:
            logger.error("Failed to get date range", error=str(e))
        
        return None
    
    def delete_dataset(
        self,
        dataset_type: str,
        symbol: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> int:
        """Delete data from storage."""
        # Implementation similar to original delete_bars
        # but generalized for any dataset type
        count = 0
        
        partition_path = self._get_partition_path(dataset_type, symbol)
        if not partition_path.exists():
            return 0
        
        files = list(partition_path.rglob("*.parquet"))
        
        for file_path in files:
            try:
                df = pd.read_parquet(file_path)
                
                if "timestamp" in df.columns and (start or end):
                    mask = pd.Series([True] * len(df), index=df.index)
                    if start:
                        mask &= df["timestamp"] >= start
                    if end:
                        mask &= df["timestamp"] <= end
                    
                    df = df[~mask]
                    count += mask.sum()
                else:
                    # Delete entire file
                    count += len(df)
                    df = pd.DataFrame()
                
                if df.empty:
                    file_path.unlink()
                else:
                    df.to_parquet(file_path, compression=self.compression)
                    
            except Exception as e:
                logger.error(
                    "Failed to delete from file",
                    file=str(file_path),
                    error=str(e),
                )
        
        return count


__all__ = ["DataStore"]
