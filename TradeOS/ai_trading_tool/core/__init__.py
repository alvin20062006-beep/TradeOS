"""Compatibility shim mapping ``ai_trading_tool.core`` to the local ``core`` tree."""

from __future__ import annotations

from pathlib import Path

_CORE_ROOT = Path(__file__).resolve().parents[2] / "core"
__path__ = [str(_CORE_ROOT)]

