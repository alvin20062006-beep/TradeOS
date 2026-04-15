"""
Signal Export Module
====================
Export SignalCandidate to various formats.

Supports:
    - JSON export
    - CSV export
    - Configurable filtering (top_k, score_threshold)

C4 Constraint: Exported signals must NOT contain execution-layer fields.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field

from ..models import SignalCandidate


# ─────────────────────────────────────────────────────────────────
# SignalExportConfig
# ─────────────────────────────────────────────────────────────────


class SignalExportConfig(BaseModel):
    """
    Configuration for signal export.

    Attributes
    ----------
    format : str
        Output format: "json" or "csv".
    include_metadata : bool
        Whether to include metadata in export.
    top_k : int, optional
        Export only top-K signals by |score|.
    score_threshold : float, optional
        Export only signals with |score| >= threshold.
    output_dir : str
        Directory for output files.
    filename_prefix : str
        Prefix for output filename.
    """

    format: Literal["json", "csv"] = "json"
    include_metadata: bool = True
    top_k: Optional[int] = None
    score_threshold: Optional[float] = None
    output_dir: str = str(Path.home() / ".ai-trading-tool" / "exports" / "signals")
    filename_prefix: str = "signals"

    class Config:
        extra = "forbid"


# ─────────────────────────────────────────────────────────────────
# Execution-layer field check (C4 constraint)
# ─────────────────────────────────────────────────────────────────


_EXECUTION_LAYER_FIELDS: frozenset[str] = frozenset([
    "order_type",
    "execution_algo",
    "position_size",
    "stop_loss",
    "take_profit",
    "leverage",
    "margin_ratio",
    "order_side",
    "order_quantity",
    "order_price",
])


def _validate_no_execution_fields(signal: SignalCandidate) -> None:
    """Raise ValueError if signal contains execution-layer fields."""
    violations = []

    # Check top-level
    for field in _EXECUTION_LAYER_FIELDS:
        if hasattr(signal, field) and getattr(signal, field) is not None:
            violations.append(f"Field '{field}' must not be set")

    # Check metadata
    meta = signal.metadata or {}
    for field in _EXECUTION_LAYER_FIELDS:
        if field in meta:
            violations.append(f"Field '{field}' found in metadata")

    if violations:
        raise ValueError(
            f"C4 constraint violation for {signal.candidate_id}:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# ─────────────────────────────────────────────────────────────────
# SignalExporter
# ─────────────────────────────────────────────────────────────────


class SignalExporter:
    """
    Export SignalCandidates to JSON or CSV.

    Parameters
    ----------
    config : SignalExportConfig
    """

    def __init__(self, config: Optional[SignalExportConfig] = None):
        self.config = config or SignalExportConfig()
        self._output_dir = Path(self.config.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        signals: list[SignalCandidate],
        experiment_id: str,
    ) -> Path:
        """
        Export signals to file.

        Parameters
        ----------
        signals : list[SignalCandidate]
        experiment_id : str

        Returns
        -------
        Path
            Path to exported file.
        """
        # Validate C4 constraint
        for sig in signals:
            _validate_no_execution_fields(sig)

        # Filter by score_threshold
        if self.config.score_threshold is not None:
            signals = [
                s for s in signals
                if abs(s.score) >= self.config.score_threshold
            ]

        # Filter by top_k
        if self.config.top_k is not None:
            signals = sorted(signals, key=lambda s: abs(s.score), reverse=True)
            signals = signals[:self.config.top_k]

        # Export
        if self.config.format == "json":
            return self._export_json(signals, experiment_id)
        else:
            return self._export_csv(signals, experiment_id)

    def _export_json(
        self,
        signals: list[SignalCandidate],
        experiment_id: str,
    ) -> Path:
        """Export to JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config.filename_prefix}_{experiment_id[:8]}_{timestamp}.json"
        path = self._output_dir / filename

        data = {
            "experiment_id": experiment_id,
            "exported_at": datetime.now().isoformat(),
            "n_signals": len(signals),
            "signals": [s.model_dump() for s in signals],
        }

        if not self.config.include_metadata:
            for sig in data["signals"]:
                sig.pop("metadata", None)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        return path

    def _export_csv(
        self,
        signals: list[SignalCandidate],
        experiment_id: str,
    ) -> Path:
        """Export to CSV."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config.filename_prefix}_{experiment_id[:8]}_{timestamp}.csv"
        path = self._output_dir / filename

        # Flatten to DataFrame
        records = []
        for sig in signals:
            record = {
                "candidate_id": sig.candidate_id,
                "experiment_id": sig.experiment_id,
                "model_artifact_id": sig.model_artifact_id,
                "symbol": sig.symbol,
                "timestamp": sig.timestamp,
                "score": sig.score,
                "score_normalized": sig.score_normalized,
                "direction_hint": sig.direction_hint,
                "confidence": sig.confidence,
                "horizon": sig.horizon,
            }
            if self.config.include_metadata:
                record["metadata"] = json.dumps(sig.metadata, default=str)
            records.append(record)

        df = pd.DataFrame(records)
        df.to_csv(path, index=False, encoding="utf-8")

        return path

    def to_dataframe(
        self,
        signals: list[SignalCandidate],
    ) -> pd.DataFrame:
        """
        Convert signals to DataFrame without file export.

        Parameters
        ----------
        signals : list[SignalCandidate]

        Returns
        -------
        pd.DataFrame
        """
        records = []
        for sig in signals:
            record = {
                "candidate_id": sig.candidate_id,
                "experiment_id": sig.experiment_id,
                "model_artifact_id": sig.model_artifact_id,
                "symbol": sig.symbol,
                "timestamp": sig.timestamp,
                "score": sig.score,
                "score_normalized": sig.score_normalized,
                "direction_hint": sig.direction_hint,
                "confidence": sig.confidence,
                "horizon": sig.horizon,
            }
            if self.config.include_metadata:
                record.update(sig.metadata or {})
            records.append(record)

        return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────


def export_signals(
    signals: list[SignalCandidate],
    experiment_id: str,
    format: Literal["json", "csv"] = "json",
    output_dir: Optional[str] = None,
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
) -> Path:
    """
    Convenience function to export signals.

    Parameters
    ----------
    signals : list[SignalCandidate]
    experiment_id : str
    format : str
    output_dir : str, optional
    top_k : int, optional
    score_threshold : float, optional

    Returns
    -------
    Path
    """
    config = SignalExportConfig(
        format=format,
        output_dir=output_dir or str(Path.home() / ".ai-trading-tool" / "exports" / "signals"),
        top_k=top_k,
        score_threshold=score_threshold,
    )
    exporter = SignalExporter(config)
    return exporter.export(signals, experiment_id)
