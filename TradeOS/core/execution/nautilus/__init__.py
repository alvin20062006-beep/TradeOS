"""Lazy Nautilus adapter exports."""

from __future__ import annotations

from importlib import import_module

from core.execution.nautilus.instrument_mapper import InstrumentMapper, NAUTILUS_AVAILABLE

_EXPORTS = {
    "OrderAdapter": ("core.execution.nautilus.order_adapter", "OrderAdapter"),
    "OrderAdapterConfig": ("core.execution.nautilus.order_adapter", "OrderAdapterConfig"),
    "FillAdapter": ("core.execution.nautilus.fill_adapter", "FillAdapter"),
    "DataAdapter": ("core.execution.nautilus.data_adapter", "DataAdapter"),
}

__all__ = [
    "InstrumentMapper",
    "NAUTILUS_AVAILABLE",
    "OrderAdapter",
    "OrderAdapterConfig",
    "FillAdapter",
    "DataAdapter",
]


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
