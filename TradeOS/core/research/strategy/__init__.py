"""
core.research.strategy
=====================
Research-layer strategy definitions.

Provides:
- StrategySignal: signal container for research outputs
- StrategyBase: abstract strategy base class

No execution-layer trading fields are exposed here.
"""

from __future__ import annotations

from core.research.strategy.base import StrategyBase
from core.research.strategy.signal import StrategySignal

__all__ = [
    "StrategySignal",
    "StrategyBase",
]
