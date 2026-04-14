"""
Deployment Candidates
====================
SignalExporter and DeploymentExporter: research result exporters only.

Scope (enforced)
----------------
These are pure schema exporters. They do NOT:
- Execute real orders
- Submit deployment approvals
- Manage approval workflows
- Trigger live trading
- Interact with broker/execution APIs

Their sole responsibility: assemble the correct internal schema objects
(SignalCandidate, DeploymentCandidate) from experiment outputs.

See docs/architecture/research_io_contract.md for the research-layer
export semantics.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

import pandas as pd

from ..models import (
    DeploymentCandidate,
    ResearchExperimentRecord,
    ModelArtifact,
    SignalCandidate,
)


# ─────────────────────────────────────────────────────────────────
# C4 constraint verification
# ─────────────────────────────────────────────────────────────────

# Fields that MUST NOT appear in SignalCandidate (execution layer fields).
# This list is checked by SignalExporter.validate_schema().
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


# ─────────────────────────────────────────────────────────────────
# SignalExporter
# ─────────────────────────────────────────────────────────────────

class SignalExporter:
    """
    Export experiment predictions as SignalCandidate objects.

    Scope
    -----
    Pure exporter. No execution, no approval, no side effects.

    Responsibilities
    ---------------
    1. Take ResearchExperimentRecord + predictions DataFrame → list[SignalCandidate]
    2. Validate SignalCandidate schema (C4 constraint check)
    3. Optionally persist signals to JSON for downstream consumption

    Usage
    -----
    exporter = SignalExporter()
    signals = exporter.from_predictions(
        experiment_id="exp_xxx",
        model_artifact_id="art_yyy",
        predictions_df=predictions_df,
        top_n=50,
    )
    """

    def __init__(
        self,
        export_dir: Optional[Path] = None,
    ):
        """
        Parameters
        ----------
        export_dir : Path, optional
            Directory to write signal JSON files.
            Default: ~/.ai-trading-tool/exports/signals/
        """
        if export_dir is None:
            export_dir = Path.home() / ".ai-trading-tool" / "exports" / "signals"
        self._export_dir = Path(export_dir)

    def from_predictions(
        self,
        experiment_id: str,
        model_artifact_id: str,
        predictions: pd.DataFrame,
        top_n: Optional[int] = None,
        score_col: str = "score",
        symbol_col: str = "symbol",
        timestamp_col: str = "timestamp",
        label_col: Optional[str] = None,
    ) -> list[SignalCandidate]:
        """
        Generate SignalCandidates from a predictions DataFrame.

        Parameters
        ----------
        experiment_id, model_artifact_id : str
        predictions : pd.DataFrame
            Columns: symbol, timestamp, score[, label]
        top_n : int, optional
            Return top-N signals by |score| descending.
        score_col, symbol_col, timestamp_col, label_col : str

        Returns
        -------
        list[SignalCandidate]
        """
        df = predictions.copy()

        required = {symbol_col, timestamp_col, score_col}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"predictions missing required columns: {missing}. "
                f"Available: {list(df.columns)}"
            )

        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        df = df.sort_values(score_col, key=lambda x: x.abs(), ascending=False)
        if top_n is not None:
            df = df.head(top_n)

        max_abs = df[score_col].abs().max() + 1e-9
        signals: list[SignalCandidate] = []

        for _, row in df.iterrows():
            score = float(row[score_col])

            # Direction hint
            if label_col and label_col in df.columns:
                label = float(row.get(label_col, 0.0))
                if pd.notna(label):
                    direction: Literal["long", "short", "neutral"] = (
                        "long" if score * label > 0 else ("short" if score * label < 0 else "neutral")
                    )
                else:
                    direction = "long" if score > 0 else ("short" if score < 0 else "neutral")
            else:
                direction = "long" if score > 0 else ("short" if score < 0 else "neutral")

            confidence = min(float(abs(score) / max_abs), 1.0)

            # Feature snapshot
            feature_snapshot: Optional[dict[str, float]] = None
            factor_cols = [
                c for c in df.columns
                if c not in {symbol_col, timestamp_col, score_col, label_col}
            ]
            if factor_cols:
                feature_snapshot = {
                    c: float(row[c])
                    for c in factor_cols
                    if pd.notna(row.get(c))
                }

            sig = SignalCandidate(
                candidate_id=f"sig_{experiment_id[:8]}_{row[symbol_col]}_{int(row[timestamp_col].timestamp())}",
                experiment_id=experiment_id,
                model_artifact_id=model_artifact_id,
                symbol=str(row[symbol_col]),
                timestamp=pd.to_datetime(row[timestamp_col]),
                score=score,
                score_normalized=float(row[score_col]) / max_abs if max_abs != 0 else 0.0,
                direction_hint=direction,
                confidence=confidence,
                horizon=1,
                feature_snapshot=feature_snapshot,
                metadata={
                    "generated_at": datetime.now().isoformat(),
                    "score_col": score_col,
                    "exported_by": "SignalExporter",
                },
            )
            signals.append(sig)

        # Validate C4 constraint
        self.validate_schema(signals)

        return signals

    def validate_schema(self, signals: list[SignalCandidate]) -> None:
        """
        Verify SignalCandidate objects contain no execution-layer fields.

        C4 constraint: SignalCandidate must NOT contain fields like
        order_type, execution_algo, position_size, stop_loss, etc.

        Parameters
        ----------
        signals : list[SignalCandidate]

        Raises
        ------
        ValueError if any execution-layer field is found in signal metadata.
        """
        violations: list[str] = []

        for sig in signals:
            # Check top-level fields
            for field in _EXECUTION_LAYER_FIELDS:
                if hasattr(sig, field) and getattr(sig, field) is not None:
                    violations.append(
                        f"SignalCandidate {sig.candidate_id}: "
                        f"execution-layer field {field!r} must not be set."
                    )
            # Check metadata dict
            meta = sig.metadata or {}
            for field in _EXECUTION_LAYER_FIELDS:
                if field in meta:
                    violations.append(
                        f"SignalCandidate {sig.candidate_id}: "
                        f"execution-layer field {field!r} found in metadata."
                    )

        if violations:
            raise ValueError(
                "C4 constraint violation — execution-layer fields in SignalCandidate:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    def to_json(
        self,
        signals: list[SignalCandidate],
        experiment_id: str,
        path: Optional[Path] = None,
    ) -> Path:
        """
        Persist signals to JSON.

        Parameters
        ----------
        signals : list[SignalCandidate]
        experiment_id : str
        path : Path, optional

        Returns
        -------
        Path to the written file.
        """
        if path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._export_dir / f"signals_{experiment_id[:8]}_{ts}.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "experiment_id": experiment_id,
            "exported_at": datetime.now().isoformat(),
            "signal_count": len(signals),
            "signals": [s.model_dump(mode="json") for s in signals],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

        return path


# ─────────────────────────────────────────────────────────────────
# DeploymentExporter
# ─────────────────────────────────────────────────────────────────

class DeploymentExporter:
    """
    Export experiment results as DeploymentCandidate objects.

    Scope
    -----
    Pure exporter. No execution, no approval, no live trading.

    Responsibilities
    ---------------
    1. Take ResearchExperimentRecord + ModelArtifact + metrics → DeploymentCandidate
    2. Add comparison_to_baseline (optional)
    3. Validate schema
    4. Optionally persist to JSON

    The approval_status is always "pending" — real approval workflow
    is handled by downstream systems.
    """

    def __init__(
        self,
        export_dir: Optional[Path] = None,
    ):
        """
        Parameters
        ----------
        export_dir : Path, optional
            Directory to write deployment candidate JSON files.
            Default: ~/.ai-trading-tool/exports/deployments/
        """
        if export_dir is None:
            export_dir = Path.home() / ".ai-trading-tool" / "exports" / "deployments"
        self._export_dir = Path(export_dir)

    def from_experiment(
        self,
        experiment: ResearchExperimentRecord,
        model_artifact: ModelArtifact,
        signals: list[SignalCandidate],
        baseline_metrics: Optional[dict[str, float]] = None,
        metrics_threshold: Optional[dict[str, float]] = None,
    ) -> DeploymentCandidate:
        """
        Build a DeploymentCandidate from experiment outputs.

        Parameters
        ----------
        experiment : ResearchExperimentRecord
        model_artifact : ModelArtifact
        signals : list[SignalCandidate]
        baseline_metrics : dict[str, float], optional
            Metrics from a reference baseline for comparison.
        metrics_threshold : dict[str, float], optional
            Minimum metric thresholds for informational flagging.

        Returns
        -------
        DeploymentCandidate
            Always with approval_status="pending".
        """
        metrics = experiment.metrics or {}

        # Gate (informational only — no approval logic)
        threshold = metrics_threshold or {}
        is_promoting = (
            metrics.get("ic", 0.0) >= threshold.get("min_ic", 0.0)
            and metrics.get("rank_ic", 0.0) >= threshold.get("min_rank_ic", 0.0)
            and metrics.get("sharpe", -999.0) >= threshold.get("min_sharpe", -999.0)
        )

        # Build comparison dict
        comparison: dict[str, float] = {}
        if baseline_metrics:
            for key in ["ic", "rank_ic", "sharpe", "max_drawdown", "hit_rate", "calmar"]:
                if key in metrics and key in baseline_metrics:
                    comparison[f"delta_{key}"] = metrics[key] - baseline_metrics[key]

        symbols = sorted(set(s.symbol for s in signals)) if signals else []

        deployment = DeploymentCandidate(
            deployment_id=f"dep_{experiment.experiment_id[:8]}",
            experiment_id=experiment.experiment_id,
            model_artifact_id=model_artifact.artifact_id,
            approval_status="pending",
            metrics_snapshot=metrics,
            comparison_to_baseline=comparison,
            symbols=symbols,
            valid_from=datetime.now(),
            valid_until=None,
            notes=(
                "Research-layer deployment candidate. "
                f"experiment_id={experiment.experiment_id}, "
                f"signals={len(signals)}, "
                f"symbols={len(symbols)}, "
                f"is_promoting={is_promoting}. "
                "Human review required before live trading."
            ),
            exported_at=datetime.now(),
            metadata={
                "is_promoting": is_promoting,
                "threshold": threshold,
                "baseline_metrics": baseline_metrics or {},
                "exported_by": "DeploymentExporter",
            },
        )

        self.validate_schema(deployment)
        return deployment

    def validate_schema(self, deployment: DeploymentCandidate) -> None:
        """
        Basic schema validation for a DeploymentCandidate.

        Checks:
        - approval_status is a valid literal value
        - metrics_snapshot is non-empty dict

        Parameters
        ----------
        deployment : DeploymentCandidate

        Raises
        ------
        ValueError on validation failure.
        """
        valid_statuses = {"pending", "approved", "rejected", "recalled"}
        if deployment.approval_status not in valid_statuses:
            raise ValueError(
                f"Invalid approval_status: {deployment.approval_status!r}. "
                f"Must be one of: {valid_statuses}"
            )

        if not isinstance(deployment.metrics_snapshot, dict):
            raise ValueError(
                "metrics_snapshot must be a dict. "
                f"Got: {type(deployment.metrics_snapshot)}"
            )

    def to_json(
        self,
        deployment: DeploymentCandidate,
        path: Optional[Path] = None,
    ) -> Path:
        """
        Persist a DeploymentCandidate to JSON.

        Parameters
        ----------
        deployment : DeploymentCandidate
        path : Path, optional

        Returns
        -------
        Path to the written file.
        """
        if path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._export_dir / f"deployment_{deployment.deployment_id}_{ts}.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(deployment.model_dump_json(indent=2))

        return path
