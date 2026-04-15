"""
ExperimentRegistry
=================
Manages ResearchExperimentRecord lifecycle:
    register() -> get() -> list() -> top_experiments()

NOTE: Renamed ExperimentRecord -> ResearchExperimentRecord to avoid
naming conflict with Phase 1 core/schemas/ExperimentRecord.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ResearchExperimentRecord


_REGISTRY_DIR_ENV = "AI_TRADING_TOOL_EXPERIMENT_REGISTRY_DIR"


class ExperimentRegistry:
    """
    Manages ResearchExperimentRecord records.

    Storage
    -------
    registry_dir/
        experiments/
            {experiment_id}.json
        index.json
    """

    def __init__(self, registry_dir: Optional[Path] = None):
        if registry_dir is None:
            import os
            default = os.environ.get(_REGISTRY_DIR_ENV)
            if default:
                registry_dir = Path(default)
            else:
                registry_dir = Path.home() / ".ai-trading-tool" / "experiment_registry"

        self._registry_dir = Path(registry_dir)
        self._experiments_dir = self._registry_dir / "experiments"
        self._index_path = self._registry_dir / "index.json"

        self._cache: dict[str, ResearchExperimentRecord] = {}

        self._ensure_dirs()
        self._load_index()

    def _ensure_dirs(self) -> None:
        self._experiments_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        if self._index_path.exists():
            with open(self._index_path, "r", encoding="utf-8") as f:
                ids = json.load(f)
                for eid in ids:
                    path = self._experiments_dir / f"{eid}.json"
                    if path.exists():
                        try:
                            with open(path, "r", encoding="utf-8") as ef:
                                self._cache[eid] = ResearchExperimentRecord.model_validate_json(ef.read())
                        except Exception as e:
                            # Skip corrupted/legacy entries that fail validation
                            import logging
                            logging.warning(f"Skipping corrupted experiment entry {eid}: {e}")
                            continue

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(list(self._cache.keys()), f)

    # ── CRUD ──────────────────────────────────────────────────────

    def register(self, experiment: ResearchExperimentRecord) -> str:
        """
        Register a new ResearchExperimentRecord.

        Returns
        -------
        experiment_id : str
        """
        experiment.experiment_id = experiment.experiment_id or str(uuid.uuid4())
        self._cache[experiment.experiment_id] = experiment

        path = self._experiments_dir / f"{experiment.experiment_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(experiment.model_dump_json(indent=2, exclude_none=True))

        self._save_index()
        return experiment.experiment_id

    def get(self, experiment_id: str) -> Optional[ResearchExperimentRecord]:
        """Retrieve an experiment by ID."""
        if experiment_id in self._cache:
            return self._cache[experiment_id]
        path = self._experiments_dir / f"{experiment_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                exp = ResearchExperimentRecord.model_validate_json(f.read())
                self._cache[experiment_id] = exp
                return exp
        return None

    def list(
        self,
        status: Optional[str] = None,
        model_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[ResearchExperimentRecord]:
        """
        List experiments, optionally filtered.
        Sorted by created_at descending.
        """
        results = list(self._cache.values())
        if status:
            results = [e for e in results if e.status == status]
        if model_name:
            results = [e for e in results if e.model_name == model_name]
        results.sort(key=lambda e: e.created_at, reverse=True)
        if limit:
            results = results[:limit]
        return results

    def top_experiments(
        self,
        metric: str = "rank_ic",
        limit: int = 10,
        min_status: str = "completed",
    ) -> list[ResearchExperimentRecord]:
        """
        Return top experiments sorted by a given metric.

        Parameters
        ----------
        metric : str
            Metric key in experiment.metrics dict.
        limit : int
            Number of top results.
        min_status : str
            Minimum status to include.
        """
        results = [
            e for e in self._cache.values()
            if e.status == min_status and metric in e.metrics
        ]
        results.sort(key=lambda e: e.metrics.get(metric, float("-inf")), reverse=True)
        return results[:limit]

    def update(
        self,
        experiment_id: str,
        **updates,
    ) -> Optional[ResearchExperimentRecord]:
        """
        Update experiment fields and persist.
        """
        exp = self.get(experiment_id)
        if exp is None:
            return None
        for k, v in updates.items():
            if hasattr(exp, k):
                setattr(exp, k, v)
        self.register(exp)
        return exp
