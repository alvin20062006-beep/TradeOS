"""
AlphaFactorRegistry
====================
Registry for alpha factor definitions and factor sets.

Provides:
    register_factor()      - register a new AlphaFactorSpec
    get_factor()           - retrieve by factor_id
    list_factors()         - list all, optionally filtered by group/layer
    search_factors()        - search by name tag
    register_set()          - register an AlphaFactorSet
    get_set()              - retrieve by set_id
    list_sets()            - list all sets
    update_factor()         - update an existing factor (bump version)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    AlphaFactorSet,
    AlphaFactorSpec,
)


_REGISTRY_DIR_ENV = "AI_TRADING_TOOL_ALPHA_REGISTRY_DIR"


class AlphaRegistry:
    """
    In-memory + filesystem-backed alpha factor registry.

    Storage layout
    --------------
    registry_dir/
        factors/
            {factor_id}.json
        sets/
            {factor_set_id}.json
        index.json          # name -> factor_id lookup
    """

    def __init__(self, registry_dir: Optional[Path] = None):
        if registry_dir is None:
            import os
            default = os.environ.get(_REGISTRY_DIR_ENV)
            if default:
                registry_dir = Path(default)
            else:
                registry_dir = Path.home() / ".ai-trading-tool" / "alpha_registry"

        self._registry_dir = Path(registry_dir)
        self._factors_dir = self._registry_dir / "factors"
        self._sets_dir = self._registry_dir / "sets"
        self._index_path = self._registry_dir / "index.json"

        # In-memory cache
        self._factors: dict[str, AlphaFactorSpec] = {}
        self._factor_index: dict[str, str] = {}  # name -> factor_id
        self._sets: dict[str, AlphaFactorSet] = {}

        self._ensure_dirs()
        self._load_index()

    # ── Internal ────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        self._factors_dir.mkdir(parents=True, exist_ok=True)
        self._sets_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        if self._index_path.exists():
            with open(self._index_path, "r", encoding="utf-8") as f:
                self._factor_index = json.load(f)

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._factor_index, f, ensure_ascii=False, indent=2)

    def _factor_path(self, factor_id: str) -> Path:
        return self._factors_dir / f"{factor_id}.json"

    def _set_path(self, set_id: str) -> Path:
        return self._sets_dir / f"{set_id}.json"

    # ── Factor CRUD ─────────────────────────────────────────────

    def register_factor(self, spec: AlphaFactorSpec) -> str:
        """
        Register a new AlphaFactorSpec.

        Returns
        -------
        factor_id : str
        """
        spec.factor_id = spec.factor_id or str(uuid.uuid4())
        self._factors[spec.factor_id] = spec
        self._factor_index[spec.factor_name] = spec.factor_id

        path = self._factor_path(spec.factor_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(spec.model_dump_json(indent=2, exclude_none=True))

        self._save_index()
        return spec.factor_id

    def get_factor(self, factor_id: str) -> Optional[AlphaFactorSpec]:
        """Retrieve a factor by factor_id."""
        if factor_id in self._factors:
            return self._factors[factor_id]

        path = self._factor_path(factor_id)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                spec = AlphaFactorSpec.model_validate_json(f.read())
                self._factors[factor_id] = spec
                return spec
        return None

    def list_factors(
        self,
        factor_group: Optional[str] = None,
        layer: Optional[str] = None,
    ) -> list[AlphaFactorSpec]:
        """
        List all factors, optionally filtered.

        Parameters
        ----------
        factor_group : str, optional
            Filter by group (technical / fundamental / etc.)
        layer : str, optional
            Filter by layer (L1 / L2 / L3)
        """
        specs = list(self._factors.values())

        # Lazy-load from disk
        for p in self._factors_dir.glob("*.json"):
            fid = p.stem
            if fid not in self._factors:
                with open(p, "r", encoding="utf-8") as f:
                    spec = AlphaFactorSpec.model_validate_json(f.read())
                    self._factors[fid] = spec

        specs = list(self._factors.values())

        if factor_group:
            specs = [s for s in specs if s.factor_group == factor_group]
        if layer:
            specs = [s for s in specs if s.layer == layer]

        return sorted(specs, key=lambda s: s.created_at)

    def search_factors(self, keyword: str) -> list[AlphaFactorSpec]:
        """Search factors by name keyword or tag."""
        keyword_lower = keyword.lower()
        all_factors = self.list_factors()
        return [
            s for s in all_factors
            if keyword_lower in s.factor_name.lower()
            or keyword_lower in s.factor_group.lower()
            or any(keyword_lower in t.lower() for t in s.tags)
            or keyword_lower in s.formula_description.lower()
        ]

    def update_factor(self, factor_id: str, **kwargs) -> Optional[AlphaFactorSpec]:
        """
        Update an existing factor (bump version or patch fields).

        Version is bumped automatically if not explicitly provided.
        """
        spec = self.get_factor(factor_id)
        if spec is None:
            return None

        # Bump patch version
        parts = spec.version.split(".")
        new_patch = int(parts[-1]) + 1
        new_version = ".".join(parts[:-1] + [str(new_patch)])

        update_dict = {"version": new_version, "created_at": datetime.now()}
        update_dict.update(kwargs)

        for k, v in update_dict.items():
            if hasattr(spec, k):
                setattr(spec, k, v)

        self.register_factor(spec)
        return spec

    # ── Factor Set CRUD ─────────────────────────────────────────

    def register_set(self, factor_set: AlphaFactorSet) -> str:
        """Register a new AlphaFactorSet."""
        factor_set.factor_set_id = factor_set.factor_set_id or str(uuid.uuid4())
        self._sets[factor_set.factor_set_id] = factor_set

        path = self._set_path(factor_set.factor_set_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(factor_set.model_dump_json(indent=2, exclude_none=True))

        return factor_set.factor_set_id

    def get_set(self, factor_set_id: str) -> Optional[AlphaFactorSet]:
        """Retrieve a factor set by set_id."""
        if factor_set_id in self._sets:
            return self._sets[factor_set_id]

        path = self._set_path(factor_set_id)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                fs = AlphaFactorSet.model_validate_json(f.read())
                self._sets[factor_set_id] = fs
                return fs
        return None

    def list_sets(self) -> list[AlphaFactorSet]:
        """List all registered factor sets."""
        for p in self._sets_dir.glob("*.json"):
            fsid = p.stem
            if fsid not in self._sets:
                with open(p, "r", encoding="utf-8") as f:
                    fs = AlphaFactorSet.model_validate_json(f.read())
                    self._sets[fsid] = fs
        return sorted(list(self._sets.values()), key=lambda s: s.created_at)

    def get_or_create_set(self, name: str) -> AlphaFactorSet:
        """Get existing set by name or create a new one."""
        existing = [s for s in self.list_sets() if s.name == name]
        if existing:
            return existing[0]
        new_set = AlphaFactorSet(name=name)
        self.register_set(new_set)
        return new_set
