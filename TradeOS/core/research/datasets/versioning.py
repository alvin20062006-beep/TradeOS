"""
DatasetVersion Registry
=====================
Manages DatasetVersion lifecycle:
    register() -> get() -> list() -> latest()
    bump_version() for new builds
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import DatasetVersion


_REGISTRY_DIR_ENV = "AI_TRADING_TOOL_DATASET_REGISTRY_DIR"


class DatasetVersionRegistry:
    """
    Manages DatasetVersion records with versioning and lookback.

    Storage
    -------
    registry_dir/
        versions/
            {dataset_id}_{version}.json
        index.json   # dataset_id -> latest_version
    """

    def __init__(self, registry_dir: Optional[Path] = None):
        if registry_dir is None:
            import os
            default = os.environ.get(_REGISTRY_DIR_ENV)
            if default:
                registry_dir = Path(default)
            else:
                registry_dir = Path.home() / ".ai-trading-tool" / "dataset_registry"

        self._registry_dir = Path(registry_dir)
        self._versions_dir = self._registry_dir / "versions"
        self._index_path = self._registry_dir / "index.json"

        self._cache: dict[str, DatasetVersion] = {}
        self._index: dict[str, str] = {}  # dataset_id -> latest_version

        self._ensure_dirs()
        self._load_index()

    def _ensure_dirs(self) -> None:
        self._versions_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        if self._index_path.exists():
            with open(self._index_path, "r", encoding="utf-8") as f:
                self._index = json.load(f)

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def _version_path(self, dataset_id: str, version: str) -> Path:
        return self._versions_dir / f"{dataset_id}_{version}.json"

    # ── CRUD ──────────────────────────────────────────────────────

    def register(self, dataset: DatasetVersion) -> str:
        """
        Register a new DatasetVersion.

        Returns
        -------
        dataset_id : str
        """
        dataset.dataset_id = dataset.dataset_id or str(uuid.uuid4())
        self._cache[dataset.dataset_id] = dataset
        self._index[dataset.dataset_id] = dataset.version

        path = self._version_path(dataset.dataset_id, dataset.version)
        with open(path, "w", encoding="utf-8") as f:
            f.write(dataset.model_dump_json(indent=2, exclude_none=True))

        self._save_index()
        return dataset.dataset_id

    def get(self, dataset_id: str, version: Optional[str] = None) -> Optional[DatasetVersion]:
        """
        Retrieve a dataset version.

        Parameters
        ----------
        dataset_id : str
        version : str, optional
            If None, returns the latest registered version.
        """
        if dataset_id in self._cache and (version is None or self._cache[dataset_id].version == version):
            return self._cache[dataset_id]

        if version is None:
            version = self._index.get(dataset_id)
            if version is None:
                return None

        path = self._version_path(dataset_id, version)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                ds = DatasetVersion.model_validate_json(f.read())
                self._cache[dataset_id] = ds
                return ds
        return None

    def latest(self, dataset_id: str) -> Optional[DatasetVersion]:
        """Get the latest registered version of a dataset."""
        return self.get(dataset_id)

    def list_versions(self, dataset_id: str) -> list[DatasetVersion]:
        """List all versions of a dataset."""
        prefix = f"{dataset_id}_"
        versions = []
        for p in self._versions_dir.glob(f"{prefix}*.json"):
            with open(p, "r", encoding="utf-8") as f:
                versions.append(DatasetVersion.model_validate_json(f.read()))
        return sorted(versions, key=lambda v: v.created_at)

    def list_all(self) -> list[DatasetVersion]:
        """List all latest versions across all dataset_ids."""
        results = []
        for dataset_id, version in self._index.items():
            dv = self.get(dataset_id, version)
            if dv:
                results.append(dv)
        return sorted(results, key=lambda v: v.created_at, reverse=True)

    def bump_version(self, dataset_id: str) -> str:
        """
        Create a new minor version for an existing dataset.

        e.g. 1.0.0 -> 1.1.0
        """
        current = self.get(dataset_id)
        if current is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        parts = current.version.split(".")
        new_minor = int(parts[1]) + 1
        new_version = f"{parts[0]}.{new_minor}.0"

        new_ds = DatasetVersion(
            dataset_id=dataset_id,
            name=current.name,
            version=new_version,
            symbols=current.symbols.copy(),
            frequency=current.frequency,
            start_time=current.start_time,
            end_time=current.end_time,
            feature_set_version=current.feature_set_version,
            label_set_version=current.label_set_version,
            source_provider=current.source_provider,
            source_reference=current.source_reference,
            metadata=current.metadata.copy(),
        )
        return self.register(new_ds)
