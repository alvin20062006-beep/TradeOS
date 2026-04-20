"""
Data Validator - Quality checks for all data types.

Provides specialized validators for each data domain:
- BarValidator: OHLCV bars
- TickValidator: Tick data
- OrderBookValidator: Order book snapshots
- FundamentalsValidator: Fundamental data
- EventValidator: Macro/news/sentiment events
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

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

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a data quality issue."""
    issue_type: str
    severity: str  # "warning", "error", "critical"
    description: str
    data: Optional[Any] = None
    field: Optional[str] = None


class BaseValidator(ABC):
    """Abstract base class for all validators."""
    
    @abstractmethod
    def validate(self, data: Any) -> list[ValidationIssue]:
        """Validate data and return list of issues."""
        pass
    
    def validate_batch(self, data_list: list[Any]) -> list[ValidationIssue]:
        """Validate a batch of data."""
        issues = []
        for item in data_list:
            issues.extend(self.validate(item))
        return issues


class BarValidator(BaseValidator):
    """
    Validator for OHLCV bars.
    
    Checks:
    - OHLC validity (high >= open, close, low)
    - Price positivity
    - Volume non-negativity
    - Sequential integrity
    - Gap detection
    """
    
    # Thresholds
    MAX_PRICE_CHANGE_PCT = 0.5  # 50% intraday change
    MIN_VOLUME = 0
    MAX_GAP_MINUTES = 1440  # 24 hours for daily bars
    
    def validate(self, bar: MarketBar) -> list[ValidationIssue]:
        """Validate a single bar."""
        issues = []
        
        # Check OHLC validity
        if bar.high < bar.low:
            issues.append(ValidationIssue(
                issue_type="invalid_ohlc",
                severity="critical",
                description=f"High ({bar.high}) < Low ({bar.low})",
                data=bar,
                field="high/low",
            ))
        
        if bar.high < bar.open or bar.high < bar.close:
            issues.append(ValidationIssue(
                issue_type="invalid_high",
                severity="error",
                description=f"High ({bar.high}) < Open ({bar.open}) or Close ({bar.close})",
                data=bar,
                field="high",
            ))
        
        if bar.low > bar.open or bar.low > bar.close:
            issues.append(ValidationIssue(
                issue_type="invalid_low",
                severity="error",
                description=f"Low ({bar.low}) > Open ({bar.open}) or Close ({bar.close})",
                data=bar,
                field="low",
            ))
        
        # Check for zero/negative values
        if bar.open <= 0:
            issues.append(ValidationIssue(
                issue_type="invalid_price",
                severity="critical",
                description=f"Open price <= 0: {bar.open}",
                data=bar,
                field="open",
            ))
        
        if bar.volume < 0:
            issues.append(ValidationIssue(
                issue_type="invalid_volume",
                severity="critical",
                description=f"Negative volume: {bar.volume}",
                data=bar,
                field="volume",
            ))
        
        # Check quote volume consistency
        if bar.quote_volume is not None and bar.quote_volume < 0:
            issues.append(ValidationIssue(
                issue_type="invalid_quote_volume",
                severity="error",
                description=f"Negative quote volume: {bar.quote_volume}",
                data=bar,
                field="quote_volume",
            ))
        
        return issues
    
    def validate_sequence(
        self,
        bars: list[MarketBar],
    ) -> list[ValidationIssue]:
        """
        Validate a sequence of bars.
        
        Checks for:
        - Timestamp gaps
        - Price gaps
        - Duplicate timestamps
        """
        issues = []
        
        if not bars:
            return issues
        
        # Individual bar validation
        for bar in bars:
            issues.extend(self.validate(bar))
        
        # Check for duplicate timestamps
        timestamps = [bar.timestamp for bar in bars]
        if len(timestamps) != len(set(timestamps)):
            issues.append(ValidationIssue(
                issue_type="duplicate_timestamps",
                severity="error",
                description="Duplicate timestamps found in bar sequence",
            ))
        
        # Sequential validation
        prev_bar = None
        for bar in sorted(bars, key=lambda b: b.timestamp):
            if prev_bar is not None:
                # Check for timestamp gaps
                gap = (bar.timestamp - prev_bar.timestamp).total_seconds()
                expected_gap = self._expected_gap_seconds(prev_bar.timeframe)
                
                if gap > expected_gap * self.MAX_GAP_MINUTES:
                    issues.append(ValidationIssue(
                        issue_type="time_gap",
                        severity="warning",
                        description=f"Large time gap: {gap/3600:.1f} hours between bars",
                        data=bar,
                        field="timestamp",
                    ))
                
                # Check for price gaps
                if prev_bar.close > 0:
                    price_change = abs(bar.open - prev_bar.close) / prev_bar.close
                    if price_change > self.MAX_PRICE_CHANGE_PCT:
                        issues.append(ValidationIssue(
                            issue_type="price_gap",
                            severity="warning",
                            description=f"Large price gap: {price_change*100:.1f}% between bars",
                            data=bar,
                            field="open",
                        ))
            
            prev_bar = bar
        
        return issues
    
    def check_completeness(
        self,
        bars: list[MarketBar],
        expected_count: int,
    ) -> ValidationIssue | None:
        """Check if expected number of bars is present."""
        actual_count = len(bars)
        
        if actual_count < expected_count:
            missing = expected_count - actual_count
            return ValidationIssue(
                issue_type="missing_bars",
                severity="warning",
                description=f"Missing {missing} bars (expected {expected_count}, got {actual_count})",
            )
        
        return None
    
    def check_staleness(
        self,
        last_bar: MarketBar,
        max_age_seconds: float,
    ) -> ValidationIssue | None:
        """Check if data is stale."""
        age = (datetime.now(last_bar.timestamp.tzinfo) - last_bar.timestamp).total_seconds()
        
        if age > max_age_seconds:
            return ValidationIssue(
                issue_type="stale_data",
                severity="warning",
                description=f"Data is stale: {age/3600:.1f} hours old",
                data=last_bar,
            )
        
        return None
    
    def _expected_gap_seconds(self, timeframe: TimeFrame) -> float:
        """Get expected gap between bars in seconds."""
        gaps = {
            TimeFrame.S1: 1,
            TimeFrame.M1: 60,
            TimeFrame.M5: 300,
            TimeFrame.M15: 900,
            TimeFrame.M30: 1800,
            TimeFrame.H1: 3600,
            TimeFrame.H4: 14400,
            TimeFrame.D1: 86400,
            TimeFrame.W1: 604800,
        }
        return gaps.get(timeframe, 86400)


class TickValidator(BaseValidator):
    """
    Validator for tick data.
    
    Checks:
    - Price positivity
    - Size positivity
    - Bid/Ask consistency
    - Spread validity
    """
    
    MAX_SPREAD_PCT = 0.1  # 10% max spread
    MAX_TICK_SIZE = 1e9  # Reasonable upper limit
    
    def validate(self, tick: MarketTick) -> list[ValidationIssue]:
        """Validate a single tick."""
        issues = []
        
        # Price validation
        if tick.price <= 0:
            issues.append(ValidationIssue(
                issue_type="invalid_price",
                severity="critical",
                description=f"Tick price <= 0: {tick.price}",
                data=tick,
                field="price",
            ))
        
        # Size validation
        if tick.size <= 0:
            issues.append(ValidationIssue(
                issue_type="invalid_size",
                severity="error",
                description=f"Tick size <= 0: {tick.size}",
                data=tick,
                field="size",
            ))
        
        if tick.size > self.MAX_TICK_SIZE:
            issues.append(ValidationIssue(
                issue_type="suspicious_size",
                severity="warning",
                description=f"Suspiciously large tick size: {tick.size}",
                data=tick,
                field="size",
            ))
        
        # Bid/Ask validation
        if tick.bid is not None and tick.ask is not None:
            if tick.bid >= tick.ask:
                issues.append(ValidationIssue(
                    issue_type="invalid_spread",
                    severity="error",
                    description=f"Bid ({tick.bid}) >= Ask ({tick.ask})",
                    data=tick,
                    field="bid/ask",
                ))
            
            spread_pct = (tick.ask - tick.bid) / tick.price
            if spread_pct > self.MAX_SPREAD_PCT:
                issues.append(ValidationIssue(
                    issue_type="wide_spread",
                    severity="warning",
                    description=f"Wide spread: {spread_pct*100:.2f}%",
                    data=tick,
                    field="spread",
                ))
        
        return issues


class OrderBookValidator(BaseValidator):
    """
    Validator for order book snapshots.
    
    Checks:
    - Bid/Ask ordering
    - Price levels validity
    - Depth consistency
    - Imbalance bounds
    """
    
    MAX_LEVELS = 100
    MAX_IMBALANCE = 1.0
    
    def validate(self, snapshot: OrderBookSnapshot) -> list[ValidationIssue]:
        """Validate an order book snapshot."""
        issues = []
        
        # Check level counts
        if len(snapshot.bids) > self.MAX_LEVELS:
            issues.append(ValidationIssue(
                issue_type="too_many_bid_levels",
                severity="warning",
                description=f"Too many bid levels: {len(snapshot.bids)}",
                data=snapshot,
                field="bids",
            ))
        
        if len(snapshot.asks) > self.MAX_LEVELS:
            issues.append(ValidationIssue(
                issue_type="too_many_ask_levels",
                severity="warning",
                description=f"Too many ask levels: {len(snapshot.asks)}",
                data=snapshot,
                field="asks",
            ))
        
        # Check bid ordering (should be descending)
        if len(snapshot.bids) >= 2:
            bid_prices = [level[0] for level in snapshot.bids]
            if bid_prices != sorted(bid_prices, reverse=True):
                issues.append(ValidationIssue(
                    issue_type="invalid_bid_ordering",
                    severity="error",
                    description="Bid levels not in descending order",
                    data=snapshot,
                    field="bids",
                ))
        
        # Check ask ordering (should be ascending)
        if len(snapshot.asks) >= 2:
            ask_prices = [level[0] for level in snapshot.asks]
            if ask_prices != sorted(ask_prices):
                issues.append(ValidationIssue(
                    issue_type="invalid_ask_ordering",
                    severity="error",
                    description="Ask levels not in ascending order",
                    data=snapshot,
                    field="asks",
                ))
        
        # Check spread
        if snapshot.bids and snapshot.asks:
            best_bid = snapshot.bids[0][0]
            best_ask = snapshot.asks[0][0]
            
            if best_bid >= best_ask:
                issues.append(ValidationIssue(
                    issue_type="crossed_book",
                    severity="critical",
                    description=f"Crossed book: Bid ({best_bid}) >= Ask ({best_ask})",
                    data=snapshot,
                    field="spread",
                ))
        
        # Check imbalance bounds
        if abs(snapshot.imbalance) > self.MAX_IMBALANCE:
            issues.append(ValidationIssue(
                issue_type="invalid_imbalance",
                severity="error",
                description=f"Imbalance out of bounds: {snapshot.imbalance}",
                data=snapshot,
                field="imbalance",
            ))
        
        # Check depth consistency
        calculated_bid_depth = sum(level[1] for level in snapshot.bids)
        calculated_ask_depth = sum(level[1] for level in snapshot.asks)
        
        if abs(calculated_bid_depth - snapshot.bid_depth) > 0.01:
            issues.append(ValidationIssue(
                issue_type="bid_depth_mismatch",
                severity="warning",
                description=f"Bid depth mismatch: {calculated_bid_depth} vs {snapshot.bid_depth}",
                data=snapshot,
                field="bid_depth",
            ))
        
        if abs(calculated_ask_depth - snapshot.ask_depth) > 0.01:
            issues.append(ValidationIssue(
                issue_type="ask_depth_mismatch",
                severity="warning",
                description=f"Ask depth mismatch: {calculated_ask_depth} vs {snapshot.ask_depth}",
                data=snapshot,
                field="ask_depth",
            ))
        
        return issues


class FundamentalsValidator(BaseValidator):
    """
    Validator for fundamental data.
    
    Checks:
    - Ratio bounds
    - Metric consistency
    - Missing critical fields
    """
    
    MAX_PE_RATIO = 1000
    MIN_PE_RATIO = -100
    MAX_PB_RATIO = 100
    
    def validate(self, fundamentals: FundamentalsSnapshot) -> list[ValidationIssue]:
        """Validate fundamental snapshot."""
        issues = []
        
        # P/E ratio validation
        if fundamentals.pe_ratio is not None:
            if fundamentals.pe_ratio > self.MAX_PE_RATIO:
                issues.append(ValidationIssue(
                    issue_type="extreme_pe_ratio",
                    severity="warning",
                    description=f"Extreme P/E ratio: {fundamentals.pe_ratio}",
                    data=fundamentals,
                    field="pe_ratio",
                ))
            
            if fundamentals.pe_ratio < self.MIN_PE_RATIO:
                issues.append(ValidationIssue(
                    issue_type="invalid_pe_ratio",
                    severity="error",
                    description=f"Invalid P/E ratio: {fundamentals.pe_ratio}",
                    data=fundamentals,
                    field="pe_ratio",
                ))
        
        # P/B ratio validation
        if fundamentals.pb_ratio is not None:
            if fundamentals.pb_ratio > self.MAX_PB_RATIO:
                issues.append(ValidationIssue(
                    issue_type="extreme_pb_ratio",
                    severity="warning",
                    description=f"Extreme P/B ratio: {fundamentals.pb_ratio}",
                    data=fundamentals,
                    field="pb_ratio",
                ))
            
            if fundamentals.pb_ratio < 0:
                issues.append(ValidationIssue(
                    issue_type="negative_pb_ratio",
                    severity="error",
                    description=f"Negative P/B ratio: {fundamentals.pb_ratio}",
                    data=fundamentals,
                    field="pb_ratio",
                ))
        
        # Market cap validation
        if fundamentals.market_cap is not None and fundamentals.market_cap <= 0:
            issues.append(ValidationIssue(
                issue_type="invalid_market_cap",
                severity="error",
                description=f"Invalid market cap: {fundamentals.market_cap}",
                data=fundamentals,
                field="market_cap",
            ))
        
        # Beta validation
        if fundamentals.beta is not None:
            if fundamentals.beta < -5 or fundamentals.beta > 5:
                issues.append(ValidationIssue(
                    issue_type="extreme_beta",
                    severity="warning",
                    description=f"Extreme beta: {fundamentals.beta}",
                    data=fundamentals,
                    field="beta",
                ))
        
        # Dividend yield validation
        if fundamentals.dividend_yield is not None:
            if fundamentals.dividend_yield < 0:
                issues.append(ValidationIssue(
                    issue_type="negative_dividend_yield",
                    severity="warning",
                    description=f"Negative dividend yield: {fundamentals.dividend_yield}",
                    data=fundamentals,
                    field="dividend_yield",
                ))
            
            if fundamentals.dividend_yield > 0.5:  # 50% yield is suspicious
                issues.append(ValidationIssue(
                    issue_type="extreme_dividend_yield",
                    severity="warning",
                    description=f"Extreme dividend yield: {fundamentals.dividend_yield*100:.1f}%",
                    data=fundamentals,
                    field="dividend_yield",
                ))
        
        return issues


class EventValidator(BaseValidator):
    """
    Validator for events (macro, news, sentiment).
    
    Checks:
    - Timestamp validity
    - Required fields
    - Value ranges
    """
    
    MAX_SENTIMENT_SCORE = 1.0
    MIN_SENTIMENT_SCORE = -1.0
    
    def validate_macro(self, event: MacroEvent) -> list[ValidationIssue]:
        """Validate macro event."""
        issues = []
        
        # Check impact level
        valid_impacts = ["high", "medium", "low"]
        if event.impact not in valid_impacts:
            issues.append(ValidationIssue(
                issue_type="invalid_impact_level",
                severity="warning",
                description=f"Invalid impact level: {event.impact}",
                data=event,
                field="impact",
            ))
        
        # Check country code format
        if event.country and len(event.country) != 2:
            issues.append(ValidationIssue(
                issue_type="invalid_country_code",
                severity="warning",
                description=f"Invalid country code: {event.country}",
                data=event,
                field="country",
            ))
        
        return issues
    
    def validate_news(self, event: NewsEvent) -> list[ValidationIssue]:
        """Validate news event."""
        issues = []
        
        # Check sentiment score range
        if event.sentiment_score is not None:
            if not (self.MIN_SENTIMENT_SCORE <= event.sentiment_score <= self.MAX_SENTIMENT_SCORE):
                issues.append(ValidationIssue(
                    issue_type="sentiment_out_of_range",
                    severity="error",
                    description=f"Sentiment score out of range: {event.sentiment_score}",
                    data=event,
                    field="sentiment_score",
                ))
        
        # Check sentiment label
        if event.sentiment_label:
            valid_labels = ["bullish", "bearish", "neutral"]
            if event.sentiment_label not in valid_labels:
                issues.append(ValidationIssue(
                    issue_type="invalid_sentiment_label",
                    severity="warning",
                    description=f"Invalid sentiment label: {event.sentiment_label}",
                    data=event,
                    field="sentiment_label",
                ))
        
        # Check for empty title
        if not event.title or len(event.title.strip()) == 0:
            issues.append(ValidationIssue(
                issue_type="empty_title",
                severity="error",
                description="News event has empty title",
                data=event,
                field="title",
            ))
        
        return issues
    
    def validate_sentiment(self, event: SentimentEvent) -> list[ValidationIssue]:
        """Validate sentiment event."""
        issues = []
        
        # Check all sentiment scores are in valid range
        scores = [
            ("news_sentiment", event.news_sentiment),
            ("social_sentiment", event.social_sentiment),
            ("forum_sentiment", event.forum_sentiment),
            ("analyst_sentiment", event.analyst_sentiment),
            ("composite_sentiment", event.composite_sentiment),
        ]
        
        for field_name, score in scores:
            if not (0 <= score <= 1):
                issues.append(ValidationIssue(
                    issue_type="sentiment_out_of_range",
                    severity="error",
                    description=f"{field_name} out of range [0,1]: {score}",
                    data=event,
                    field=field_name,
                ))
        
        # Check ratio consistency
        total_ratio = event.bullish_ratio + event.bearish_ratio + event.neutral_ratio
        if abs(total_ratio - 1.0) > 0.01:
            issues.append(ValidationIssue(
                issue_type="ratio_mismatch",
                severity="warning",
                description=f"Sentiment ratios don't sum to 1: {total_ratio}",
                data=event,
                field="ratios",
            ))
        
        return issues
    
    def validate(self, data: Any) -> list[ValidationIssue]:
        """Generic validate - dispatches to appropriate method."""
        if isinstance(data, MacroEvent):
            return self.validate_macro(data)
        elif isinstance(data, NewsEvent):
            return self.validate_news(data)
        elif isinstance(data, SentimentEvent):
            return self.validate_sentiment(data)
        else:
            return [ValidationIssue(
                issue_type="unknown_event_type",
                severity="error",
                description=f"Unknown event type: {type(data)}",
                data=data,
            )]


class DataValidator:
    """
    Unified data validator that dispatches to specialized validators.
    
    Usage:
        validator = DataValidator()
        issues = validator.validate_bars(bars)
        issues = validator.validate_ticks(ticks)
        issues = validator.validate_order_book(snapshot)
    """
    
    def __init__(self):
        self.bar_validator = BarValidator()
        self.tick_validator = TickValidator()
        self.orderbook_validator = OrderBookValidator()
        self.fundamentals_validator = FundamentalsValidator()
        self.event_validator = EventValidator()
    
    def validate_bars(
        self,
        bars: list[MarketBar] | MarketBar,
    ) -> list[ValidationIssue]:
        """Validate OHLCV bars."""
        if isinstance(bars, list):
            return self.bar_validator.validate_sequence(bars)
        return self.bar_validator.validate(bars)
    
    def validate_ticks(
        self,
        ticks: list[MarketTick] | MarketTick,
    ) -> list[ValidationIssue]:
        """Validate tick data."""
        if isinstance(ticks, list):
            return self.tick_validator.validate_batch(ticks)
        return self.tick_validator.validate(ticks)
    
    def validate_order_book(
        self,
        snapshot: OrderBookSnapshot,
    ) -> list[ValidationIssue]:
        """Validate order book snapshot."""
        return self.orderbook_validator.validate(snapshot)
    
    def validate_fundamentals(
        self,
        snapshot: FundamentalsSnapshot,
    ) -> list[ValidationIssue]:
        """Validate fundamental data."""
        return self.fundamentals_validator.validate(snapshot)
    
    def validate_macro(self, event: MacroEvent) -> list[ValidationIssue]:
        """Validate macro event."""
        return self.event_validator.validate_macro(event)
    
    def validate_news(self, event: NewsEvent) -> list[ValidationIssue]:
        """Validate news event."""
        return self.event_validator.validate_news(event)
    
    def validate_sentiment(self, event: SentimentEvent) -> list[ValidationIssue]:
        """Validate sentiment event."""
        return self.event_validator.validate_sentiment(event)
    
    def validate_any(self, data: Any) -> list[ValidationIssue]:
        """Auto-detect type and validate."""
        if isinstance(data, MarketBar):
            return self.bar_validator.validate(data)
        elif isinstance(data, MarketTick):
            return self.tick_validator.validate(data)
        elif isinstance(data, OrderBookSnapshot):
            return self.orderbook_validator.validate(data)
        elif isinstance(data, FundamentalsSnapshot):
            return self.fundamentals_validator.validate(data)
        elif isinstance(data, (MacroEvent, NewsEvent, SentimentEvent)):
            return self.event_validator.validate(data)
        else:
            return [ValidationIssue(
                issue_type="unknown_data_type",
                severity="error",
                description=f"Cannot validate unknown type: {type(data)}",
                data=data,
            )]


__all__ = [
    "ValidationIssue",
    "BaseValidator",
    "BarValidator",
    "TickValidator",
    "OrderBookValidator",
    "FundamentalsValidator",
    "EventValidator",
    "DataValidator",
]

