"""Data layer package exports.

This module stays intentionally defensive because the repository contains a
mix of newer `core.*` imports and older `ai_trading_tool.*` import paths.
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from .live import LiveAnalysisOrchestrator

    __all__.append("LiveAnalysisOrchestrator")
except Exception:
    pass

try:
    from .schemas import (
        SCHEMA_TYPES,
        MARKET_DATA_SCHEMAS,
        RESEARCH_DATA_SCHEMAS,
        get_schema_type,
        list_schema_types,
    )

    __all__ += [
        "SCHEMA_TYPES",
        "MARKET_DATA_SCHEMAS",
        "RESEARCH_DATA_SCHEMAS",
        "get_schema_type",
        "list_schema_types",
    ]
except Exception:
    pass
