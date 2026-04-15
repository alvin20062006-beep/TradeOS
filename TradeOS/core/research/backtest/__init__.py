"""
core.research.backtest
=====================
Research-layer portfolio backtest engine.
"""

from __future__ import annotations

from core.research.backtest.result import BacktestResult
from core.research.backtest.cost_model import CostModel
from core.research.backtest.engine import BacktestEngine
from core.research.backtest.schema import BacktestConfig, CostModelConfig

__all__ = [
    "BacktestResult",
    "CostModel",
    "CostModelConfig",
    "BacktestConfig",
    "BacktestEngine",
]
