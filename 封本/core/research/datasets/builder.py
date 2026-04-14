"""
Dataset Builder
==============

Builds DatasetVersion from existing data layer sources.

Supported sources (Constraint 2: do NOT implement data downloaders)
------------------------------------------------------------------
1. CSV files in a directory
2. Internal DataStore (Parquet partitioned)
3. Symbol list + date range (metadata-only spec)

Builder does NOT:
- Download or fetch data from external APIs
- Implement new data provider adapters
- Re-implement DataStore or DataProvider interfaces

Responsibilities:
- Read metadata from existing data
- Assemble DatasetVersion spec
- Register version via DatasetVersionRegistry
- Write metadata files alongside data
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import pandas as pd

from ..models import DatasetVersion
from .versioning import DatasetVersionRegistry


# ── Supported source types ─────────────────────────────────────

DataSourceType = Literal["csv_dir", "parquet_dir", "symbol_list"]


class DatasetBuilder:
    """
    Builds DatasetVersion from existing data sources.

    Parameters
    ----------
    registry : DatasetVersionRegistry, optional
        Registry for storing versioned specs.
        If None, uses the default registry.
    """

    def __init__(
        self,
        registry: Optional[DatasetVersionRegistry] = None,
    ):
        if registry is None:
            registry = DatasetVersionRegistry()
        self._registry = registry

    # ── Public build methods ────────────────────────────────

    def build_from_csv_dir(
        self,
        csv_dir: Path | str,
        dataset_id: str,
        name: str,
        frequency: str = "1d",
        symbols: Optional[list[str]] = None,
        description: str = "",
    ) -> DatasetVersion:
        """
        Build a DatasetVersion from a directory of CSV files.

        CSV format expected:
            {csv_dir}/
                {symbol}.csv
            Each CSV has columns: date, open, high, low, close, volume

        Parameters
        ----------
        csv_dir : Path | str
            Directory containing per-symbol CSV files.
        dataset_id : str
            Unique identifier for this dataset.
        name : str
            Human-readable name.
        frequency : str
            Data frequency (e.g. "1d", "1m").
        symbols : list[str], optional
            Subset of symbols to include.
            If None, all .csv files in csv_dir are used.
        description : str

        Returns
        -------
        DatasetVersion
        """
        csv_dir = Path(csv_dir)

        # Discover symbols
        if symbols is None:
            symbols = [
                p.stem.upper()
                for p in csv_dir.glob("*.csv")
                if p.is_file()
            ]

        if not symbols:
            raise ValueError(f"No CSV files found in {csv_dir}")

        # Detect date range by scanning all CSVs
        start_times: list[datetime] = []
        end_times: list[datetime] = []

        for sym in symbols[:10]:  # Sample first 10 for speed
            csv_file = csv_dir / f"{sym.lower()}.csv"
            if csv_file.exists():
                df = pd.read_csv(csv_file, nrows=1, usecols=["date"])
                if not df.empty:
                    start_times.append(pd.to_datetime(df["date"].iloc[0]))

            csv_file2 = csv_dir / f"{sym.lower()}.csv"
            if csv_file2.exists():
                df_tail = pd.read_csv(csv_file2, usecols=["date"])
                if not df_tail.empty:
                    end_times.append(pd.to_datetime(df_tail["date"].iloc[-1]))

        start_time = min(start_times) if start_times else None
        end_time = max(end_times) if end_times else None

        # Build spec
        version = self._next_version(dataset_id)

        dataset = DatasetVersion(
            dataset_id=dataset_id,
            name=name,
            version=version,
            symbols=symbols,
            frequency=frequency,
            start_time=start_time,
            end_time=end_time,
            description=description,
            source_provider="csv_dir",
            source_reference=str(csv_dir),
            metadata={
                "source_type": "csv_dir",
                "symbol_count": len(symbols),
                "frequency": frequency,
            },
        )

        self._registry.register(dataset)
        return dataset

    def build_from_parquet_dir(
        self,
        parquet_dir: Path | str,
        dataset_id: str,
        name: str,
        frequency: str = "1d",
        symbols: Optional[list[str]] = None,
        description: str = "",
    ) -> DatasetVersion:
        """
        Build a DatasetVersion from internal Parquet partitioned data.

        Expected layout:
            {parquet_dir}/
                bars/{SYMBOL}/{FREQ}/YYYY-MM.parquet
                ...

        Parameters
        ----------
        parquet_dir : Path | str
            Root of the partitioned data store.
        dataset_id : str
        name : str
        frequency : str
        symbols : list[str], optional
        description : str

        Returns
        -------
        DatasetVersion
        """
        import pandas as pd

        parquet_dir = Path(parquet_dir)

        # Discover symbols from bars/ subdirectory
        bars_root = parquet_dir / "bars"
        if symbols is None:
            if bars_root.exists():
                symbols = sorted([d.name.upper() for d in bars_root.iterdir() if d.is_dir()])
            else:
                symbols = []

        if not symbols:
            raise ValueError(f"No symbols found in {parquet_dir}/bars/")

        # Detect date range
        start_time: Optional[datetime] = None
        end_time: Optional[datetime] = None

        for sym in symbols[:5]:  # Sample
            sym_dir = bars_root / sym / frequency
            if sym_dir.exists():
                files = sorted(sym_dir.glob("*.parquet"))
                if files:
                    try:
                        df_first = pd.read_parquet(files[0])
                        ts_col = "timestamp" if "timestamp" in df_first.columns else df_first.index.name
                        if ts_col:
                            if isinstance(df_first.index, pd.DatetimeIndex):
                                first_ts = df_first.index.min()
                            else:
                                first_ts = pd.to_datetime(df_first[ts_col].min())
                            if start_time is None or first_ts < start_time:
                                start_time = first_ts
                        if len(files) > 1:
                            df_last = pd.read_parquet(files[-1])
                            if isinstance(df_last.index, pd.DatetimeIndex):
                                last_ts = df_last.index.max()
                            else:
                                last_ts = pd.to_datetime(df_last[ts_col].max())
                            if end_time is None or last_ts > end_time:
                                end_time = last_ts
                    except Exception:
                        pass

        version = self._next_version(dataset_id)

        dataset = DatasetVersion(
            dataset_id=dataset_id,
            name=name,
            version=version,
            symbols=symbols,
            frequency=frequency,
            start_time=start_time,
            end_time=end_time,
            description=description,
            source_provider="parquet_dir",
            source_reference=str(parquet_dir),
            metadata={
                "source_type": "parquet_dir",
                "symbol_count": len(symbols),
                "frequency": frequency,
            },
        )

        self._registry.register(dataset)
        return dataset

    def build_metadata_only(
        self,
        dataset_id: str,
        name: str,
        symbols: list[str],
        frequency: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        description: str = "",
    ) -> DatasetVersion:
        """
        Build a DatasetVersion with only metadata (no data on disk yet).

        Use when you want to plan a dataset before data is collected.

        Parameters
        ----------
        dataset_id : str
        name : str
        symbols : list[str]
        frequency : str
        start_time : datetime
        end_time : datetime
        description : str

        Returns
        -------
        DatasetVersion
        """
        version = self._next_version(dataset_id)

        dataset = DatasetVersion(
            dataset_id=dataset_id,
            name=name,
            version=version,
            symbols=symbols,
            frequency=frequency,
            start_time=start_time,
            end_time=end_time,
            description=description,
            source_provider="metadata_only",
            source_reference="",
            metadata={
                "source_type": "metadata_only",
                "symbol_count": len(symbols),
                "frequency": frequency,
            },
        )

        self._registry.register(dataset)
        return dataset

    # ── Registry access ───────────────────────────────────

    def get(self, dataset_id: str) -> Optional[DatasetVersion]:
        """Get latest version of a dataset."""
        return self._registry.get(dataset_id)

    def list_all(self) -> list[DatasetVersion]:
        """List all registered datasets."""
        return self._registry.list_all()

    def list_versions(self, dataset_id: str) -> list[DatasetVersion]:
        """List all versions of a dataset."""
        return self._registry.list_versions(dataset_id)

    # ── Internal helpers ─────────────────────────────────

    def _next_version(self, dataset_id: str) -> str:
        """Determine next version string for a dataset."""
        existing = self._registry.get(dataset_id)
        if existing is None:
            return "1.0.0"

        parts = existing.version.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0

        # Bump minor version for new build
        return f"{major}.{minor + 1}.0"


# ── Convenience factory ─────────────────────────────────────────

def get_builder(
    registry: Optional[DatasetVersionRegistry] = None,
) -> DatasetBuilder:
    """Factory for DatasetBuilder."""
    return DatasetBuilder(registry=registry)
