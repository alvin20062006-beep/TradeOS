"""
Analysis Engine Base
===================

Unified base class for all six analysis engines in core/analysis/.
Every engine MUST inherit from AnalysisEngine and implement analyze().

Schema reference:
- EngineSignal, Direction, Regime, TimeFrame  → core/schemas/__init__.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from core.schemas import EngineSignal, MarketBar


class AnalysisEngine(ABC):
    """
    Abstract base class for all analysis engines.

    Inheritance order:
        AnalysisEngine
        └── [ChanEngine | TechnicalEngine | OrderFlowEngine |
             SentimentEngine | MacroEngine | FundamentalEngine]

    Each engine:
    - Has a unique engine_name (used in EngineSignal.engine_name)
    - Receives typed inputs (MarketBar[], FundamentalsSnapshot, etc.)
    - Returns a typed EngineSignal subclass
    """

    # Subclasses MUST set this
    engine_name: str = "base"

    # ─────────────────────────────────────────────────────────────
    # Core API
    # ─────────────────────────────────────────────────────────────

    @abstractmethod
    def analyze(self, data: Any, **kwargs: Any) -> "EngineSignal":
        """
        Analyze a single instrument and return an EngineSignal.

        Args:
            data: Typed input specific to each engine.
                  - Technical/Chan/Macro/OrderFlow → list[MarketBar]
                  - Fundamental → FundamentalsSnapshot
                  - Sentiment → list[NewsEvent] | dict with bars
            **kwargs: Engine-specific parameters.

        Returns:
            EngineSignal subclass with populated fields.

        Raises:
            ValueError: If input data is invalid.
            RuntimeError: If analysis fails (caught by wrapper, returns
                         a neutral signal with error metadata).
        """
        ...

    def batch_analyze(
        self, data_map: dict[str, Any], **kwargs: Any
    ) -> dict[str, "EngineSignal"]:
        """
        Analyze multiple instruments.

        Default implementation: sequential single-analyze.
        Subclasses may override with parallel execution.

        Args:
            data_map: {symbol: data} mapping.
            **kwargs: Passed to each analyze() call.

        Returns:
            {symbol: EngineSignal} mapping.
        """
        results: dict[str, "EngineSignal"] = {}
        for symbol, data in data_map.items():
            try:
                results[symbol] = self.analyze(data, **kwargs)
            except Exception as exc:  # noqa: BLE001
                # Wrap failure in a neutral signal so batch continues
                from core.schemas import Direction, EngineSignal, Regime

                results[symbol] = EngineSignal(
                    engine_name=self.engine_name,
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    direction=Direction.FLAT,
                    confidence=0.0,
                    regime=Regime.UNKNOWN,
                    reasoning=f"Analysis failed: {exc}",
                    metadata={"error": str(exc)},
                )
        return results

    # ─────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """
        Engine health check. Override if engine has resources to verify.

        Returns:
            True if engine is ready. False otherwise.
        """
        return True

    def warm_up(self, symbols: list[str] | None = None) -> None:
        """
        Optional warm-up hook. Called before live analysis begins.

        Subclasses can override to pre-load indicators, calibrate
        models, or fetch reference data.

        Args:
            symbols: Instruments to warm up for.
        """
        pass

    def shutdown(self) -> None:
        """
        Optional shutdown hook. Called when engine is decommissioned.

        Subclasses can override to release resources (DB connections,
        model handles, etc.).
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _check_bars(bars: Any, min_length: int = 2) -> list["MarketBar"]:
        """
        Validate and normalize bar input.

        Args:
            bars: Input data (list, single bar, or dict with 'bars' key).
            min_length: Minimum required bars.

        Returns:
            Normalized list of MarketBar.

        Raises:
            ValueError: If validation fails.
        """
        from core.schemas import MarketBar

        if bars is None:
            raise ValueError("Input data is None")

        # Unwrap if dict
        if isinstance(bars, dict):
            if "bars" in bars:
                bars = bars["bars"]
            elif "close" in bars:
                # Single-row dict → wrap in list
                bars = [bars]
        elif not isinstance(bars, (list, tuple)):
            bars = [bars]

        if not bars:
            raise ValueError("Input bars list is empty")

        if len(bars) < min_length:
            raise ValueError(
                f"Insufficient bars: got {len(bars)}, need at least {min_length}"
            )

        # Coerce dicts → MarketBar
        result: list[MarketBar] = []
        for bar in bars:
            if isinstance(bar, MarketBar):
                result.append(bar)
            elif isinstance(bar, dict):
                result.append(MarketBar(**bar))
            else:
                raise ValueError(f"Unsupported bar type: {type(bar).__name__}")

        return result

    def _require_timeframe(
        self, bars: list["MarketBar"], default: str = "1h"
    ) -> str:
        """Extract timeframe string from bars or use default."""
        if bars and hasattr(bars[0], "timeframe"):
            return bars[0].timeframe.value if hasattr(bars[0].timeframe, "value") else str(bars[0].timeframe)
        return default
