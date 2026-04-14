"""
Deployment Module
=================
Export research results for deployment.

Submodules:
    candidates.py    - SignalExporter, DeploymentExporter
    signal_export.py - SignalExporter (standalone), SignalExportConfig
"""

from .candidates import DeploymentExporter, SignalExporter
from .signal_export import (
    SignalExporter as StandaloneSignalExporter,
    SignalExportConfig,
    export_signals,
)

__all__ = [
    "SignalExporter",
    "DeploymentExporter",
    "StandaloneSignalExporter",
    "SignalExportConfig",
    "export_signals",
]
