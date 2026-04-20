"""
Data Layer Schemas - Type definitions for all data types.

This module defines the schema types used throughout the data layer.
All schemas are re-exported from core.schemas for consistency.
"""

from __future__ import annotations

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

# Schema type registry for dynamic lookup
SCHEMA_TYPES = {
    "bars": MarketBar,
    "ticks": MarketTick,
    "orderbooks": OrderBookSnapshot,
    "trades": TradePrint,
    "fundamentals": FundamentalsSnapshot,
    "macro": MacroEvent,
    "news": NewsEvent,
    "sentiment": SentimentEvent,
}

# Market data schemas (price/action related)
MARKET_DATA_SCHEMAS = {
    "bars": MarketBar,
    "ticks": MarketTick,
    "orderbooks": OrderBookSnapshot,
    "trades": TradePrint,
}

# Research data schemas (analysis related)
RESEARCH_DATA_SCHEMAS = {
    "fundamentals": FundamentalsSnapshot,
    "macro": MacroEvent,
    "news": NewsEvent,
    "sentiment": SentimentEvent,
}


def get_schema_type(dataset_type: str) -> type:
    """Get schema class by dataset type name."""
    return SCHEMA_TYPES.get(dataset_type)


def list_schema_types() -> list[str]:
    """List all supported schema type names."""
    return list(SCHEMA_TYPES.keys())


__all__ = [
    "MarketBar",
    "MarketTick",
    "OrderBookSnapshot",
    "TradePrint",
    "FundamentalsSnapshot",
    "MacroEvent",
    "NewsEvent",
    "SentimentEvent",
    "TimeFrame",
    "SCHEMA_TYPES",
    "MARKET_DATA_SCHEMAS",
    "RESEARCH_DATA_SCHEMAS",
    "get_schema_type",
    "list_schema_types",
]

