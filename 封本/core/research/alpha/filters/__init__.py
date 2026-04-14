"""
Alpha Filters
=============
Filter modules for screening and selection.

Filters return FilterResult objects and can be chained.
"""

from .schema import (
    FilterResult,
    RegulatoryFlag,
    MarketRegime,
    MarketRegimeResult,
    CompositeFilterResult,
)

__all__ = [
    "FilterResult",
    "RegulatoryFlag",
    "MarketRegime",
    "MarketRegimeResult",
    "CompositeFilterResult",
]
