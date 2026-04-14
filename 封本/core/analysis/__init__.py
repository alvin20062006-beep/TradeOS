"""
Core Analysis Engines
====================

Six analysis engines covering the complete trading analysis spectrum.

Each engine inherits from AnalysisEngine (base.py) and returns
a typed EngineSignal subclass defined in core/schemas/.

Usage:
    from core.analysis import TechnicalEngine, ChanEngine, ...

Architecture:
    analysis/
    ├── base.py           # AnalysisEngine ABC
    ├── chan/             # 缠论引擎 → ChanSignal
    ├── technical/        # 经典技术分析 → TechnicalSignal
    ├── orderflow/        # 盘口/订单流 → OrderFlowSignal
    ├── sentiment/        # 情绪/资金博弈 → SentimentEvent
    ├── macro/            # 宏观消息 → MacroSignal
    └── fundamental/      # 基本盘报表 → FundamentalReport + EngineSignal
"""

from __future__ import annotations

from core.analysis.base import AnalysisEngine

# ─────────────────────────────────────────────────────────────
# Lazy imports — avoid circular deps by importing only from sub-modules
# ─────────────────────────────────────────────────────────────

def __getattr__(name: str):
    """Lazy import for engine sub-modules."""
    mapping = {
        "ChanEngine": ".chan.engine:ChanEngine",
        "TechnicalEngine": ".technical.engine:TechnicalEngine",
        "OrderFlowEngine": ".orderflow.engine:OrderFlowEngine",
        "SentimentEngine": ".sentiment.engine:SentimentEngine",
        "MacroEngine": ".macro.engine:MacroEngine",
        "FundamentalEngine": ".fundamental.engine:FundamentalEngine",
    }
    if name in mapping:
        import importlib
        module_path, class_name = mapping[name].rsplit(":", 1)
        mod = importlib.import_module(module_path, __package__)
        return getattr(mod, class_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ─────────────────────────────────────────────────────────────
# Explicit public API (static analysis tool support)
# ─────────────────────────────────────────────────────────────

__all__ = [
    "AnalysisEngine",
    # Engines — import via lazy __getattr__ or direct sub-module import
    # "ChanEngine",
    # "TechnicalEngine",
    # "OrderFlowEngine",
    # "SentimentEngine",
    # "MacroEngine",
    # "FundamentalEngine",
]
