"""
Backfill Manager - Orchestrates data backfilling.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from ai_trading_tool.core.data.base import DataProvider
from ai_trading_tool.core.data.store import DataStore
from ai_trading_tool.core.data.validator import DataValidator
from ai_trading_tool.core.schemas import TimeFrame

logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    """Result of a backfill operation."""
    symbol: str
    timeframe: TimeFrame
    start_date: datetime
    end_date: datetime
    bars_fetched: int
    bars_written: int
    errors: list[str]
    
    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.bars_written > 0


class BackfillManager:
    """
    Manages data backfilling from providers to storage.
    """
    
    def __init__(
        self,
        provider: DataProvider,
        store: DataStore,
        validator: Optional[DataValidator] = None,
        batch_size: int = 10000,
    ):
        self.provider = provider
        self.store = store
        self.validator = validator or DataValidator()
        self.batch_size = batch_size
    
    async def backfill(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        force: bool = False,
    ) -> BackfillResult:
        """
        Backfill data for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Bar timeframe
            start_date: Start date
            end_date: End date
            force: Overwrite existing data
        
        Returns:
            BackfillResult with statistics
        """
        errors = []
        bars_fetched = 0
        bars_written = 0
        
        # Check existing data range
        existing_range = self.store.get_date_range(symbol, timeframe)
        
        if existing_range and not force:
            # Adjust start date to avoid re-fetching
            existing_start, existing_end = existing_range
            if start_date < existing_start:
                start_date = existing_start
            if end_date > existing_end:
                end_date = existing_end
        
        logger.info(
            "Starting backfill",
            symbol=symbol,
            timeframe=timeframe.value,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )
        
        try:
            # Fetch in batches to avoid rate limits
            current_start = start_date
            batch_count = 0
            
            while current_start < end_date:
                batch_end = min(
                    current_start + timedelta(days=365),  # Max 1 year per request
                    end_date
                )
                
                try:
                    # Fetch batch
                    bars = await self.provider.get_bars(
                        symbol=symbol,
                        timeframe=timeframe,
                        start=current_start,
                        end=batch_end,
                    )
                    
                    bars_fetched += len(bars)
                    
                    if bars:
                        # Validate
                        issues = self.validator.validate_bars(bars)
                        if issues:
                            for issue in issues:
                                if issue.severity == "critical":
                                    errors.append(f"{issue.issue_type}: {issue.description}")
                        
                        # Write to store
                        written = await self.store.write_bars(
                            symbol=symbol,
                            timeframe=timeframe,
                            bars=bars,
                        )
                        bars_written += written
                        
                        logger.info(
                            "Backfill batch completed",
                            symbol=symbol,
                            batch=batch_count,
                            bars=len(bars),
                        )
                    else:
                        logger.warning(
                            "No data returned for batch",
                            symbol=symbol,
                            start=current_start.isoformat(),
                            end=batch_end.isoformat(),
                        )
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    errors.append(f"Batch error: {str(e)}")
                    logger.error(
                        "Backfill batch failed",
                        symbol=symbol,
                        error=str(e),
                    )
                
                current_start = batch_end
                batch_count += 1
        
        except Exception as e:
            errors.append(f"Backfill failed: {str(e)}")
            logger.error("Backfill failed", symbol=symbol, error=str(e))
        
        result = BackfillResult(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            bars_fetched=bars_fetched,
            bars_written=bars_written,
            errors=errors,
        )
        
        logger.info(
            "Backfill completed",
            symbol=symbol,
            success=result.success,
            fetched=bars_fetched,
            written=bars_written,
            errors=len(errors),
        )
        
        return result
    
    async def backfill_multiple(
        self,
        symbols: list[str],
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        max_concurrent: int = 3,
    ) -> list[BackfillResult]:
        """
        Backfill data for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            timeframe: Bar timeframe
            start_date: Start date
            end_date: End date
            max_concurrent: Maximum concurrent backfill operations
        
        Returns:
            List of BackfillResult
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def backfill_one(symbol: str) -> BackfillResult:
            async with semaphore:
                return await self.backfill(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                )
        
        tasks = [backfill_one(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(BackfillResult(
                    symbol=symbols[i],
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    bars_fetched=0,
                    bars_written=0,
                    errors=[str(result)],
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_stats(self) -> dict:
        """Get backfill statistics."""
        return {
            "symbols": self.store.list_symbols(),
            "provider": self.provider.name,
        }
