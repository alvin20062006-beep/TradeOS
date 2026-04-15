"""
Unit tests for datasets/builder.py
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import time


class TestDatasetBuilder:
    """Tests for DatasetBuilder."""

    def test_build_metadata_only(self):
        """B1: build_metadata_only creates and registers a DatasetVersion."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.datasets.builder import DatasetBuilder

        # Use timestamp-based unique ID to avoid persistent-registry pollution
        unique_id = f"test_ds_b2b_md_{int(time.time() * 1000)}"

        builder = DatasetBuilder()
        ds = builder.build_metadata_only(
            dataset_id=unique_id,
            name="Test Dataset",
            symbols=["AAPL", "MSFT"],
            frequency="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
            description="Test",
        )

        assert ds.dataset_id == unique_id
        assert ds.name == "Test Dataset"
        assert ds.symbols == ["AAPL", "MSFT"]
        assert ds.frequency == "1d"
        assert ds.start_time == datetime(2024, 1, 1)
        assert ds.end_time == datetime(2024, 12, 31)
        assert ds.version == "1.0.0"
        assert ds.metadata["source_type"] == "metadata_only"

    def test_version_bump(self):
        """B1: Bumping version increments correctly."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.datasets.builder import DatasetBuilder

        # Unique ID to avoid cross-test pollution
        unique_id = f"test_ds_bump_b2b_{int(time.time() * 1000)}"

        builder = DatasetBuilder()
        v1 = builder.build_metadata_only(
            dataset_id=unique_id,
            name="Bump Test",
            symbols=["AAPL"],
            frequency="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 6, 30),
        )

        v2 = builder.build_metadata_only(
            dataset_id=unique_id,
            name="Bump Test v2",
            symbols=["AAPL", "MSFT"],
            frequency="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )

        assert v1.version == "1.0.0"
        assert v2.version == "1.1.0"

    def test_build_from_csv_dir_basic(self):
        """B2: build_from_csv_dir detects symbols and date range."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.datasets.builder import DatasetBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "aapl.csv").write_text(
                "date,open,high,low,close,volume\n"
                "2024-01-02,185.0,186.0,184.0,185.5,50000000\n"
                "2024-01-03,186.0,187.0,185.5,186.2,48000000\n"
            )
            (tmp / "msft.csv").write_text(
                "date,open,high,low,close,volume\n"
                "2024-01-02,370.0,372.0,369.0,371.0,20000000\n"
                "2024-01-03,372.0,373.0,371.0,372.5,21000000\n"
            )
            builder = DatasetBuilder()
            ds = builder.build_from_csv_dir(
                csv_dir=tmp,
                dataset_id=f"test_csv_{int(time.time() * 1000)}",
                name="CSV Test",
                frequency="1d",
            )
            assert set(ds.symbols) == {"AAPL", "MSFT"}
            assert ds.frequency == "1d"
            assert ds.source_provider == "csv_dir"
            assert ds.start_time is not None
            assert ds.end_time is not None

    def test_build_from_csv_dir_subset_symbols(self):
        """B2: build_from_csv_dir with explicit symbol subset."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.datasets.builder import DatasetBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "aapl.csv").write_text(
                "date,open,high,low,close,volume\n"
                "2024-01-02,185.0,186.0,184.0,185.5,50000000\n"
            )
            (tmp / "msft.csv").write_text(
                "date,open,high,low,close,volume\n"
                "2024-01-02,370.0,372.0,369.0,371.0,20000000\n"
            )
            builder = DatasetBuilder()
            ds = builder.build_from_csv_dir(
                csv_dir=tmp,
                dataset_id=f"test_subset_{int(time.time() * 1000)}",
                name="Subset",
                frequency="1d",
                symbols=["AAPL"],
            )
            assert ds.symbols == ["AAPL"]

    def test_build_from_csv_dir_no_files_raises(self):
        """B2: build_from_csv_dir raises if no CSV files found."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.datasets.builder import DatasetBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DatasetBuilder()
            with pytest.raises(ValueError, match="No CSV files"):
                builder.build_from_csv_dir(
                    csv_dir=tmpdir,
                    dataset_id=f"test_empty_{int(time.time() * 1000)}",
                    name="Empty",
                    frequency="1d",
                )

    def test_registry_access(self):
        """B3: Registry access methods work."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.datasets.builder import DatasetBuilder

        unique_id = f"test_reg_b2b_{int(time.time() * 1000)}"
        builder = DatasetBuilder()
        ds = builder.build_metadata_only(
            dataset_id=unique_id,
            name="Registry Test",
            symbols=["AAPL"],
            frequency="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 6, 30),
        )
        retrieved = builder.get(unique_id)
        assert retrieved is not None
        assert retrieved.dataset_id == unique_id
        assert retrieved.version == ds.version

    def test_list_all(self):
        """B3: list_all returns all registered datasets."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.datasets.builder import DatasetBuilder

        uid1 = f"list_t1_{int(time.time() * 1000)}"
        uid2 = f"list_t2_{int(time.time() * 1000)}"
        builder = DatasetBuilder()
        builder.build_metadata_only(
            dataset_id=uid1,
            name="List Test 1",
            symbols=["AAPL"],
            frequency="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 6, 30),
        )
        builder.build_metadata_only(
            dataset_id=uid2,
            name="List Test 2",
            symbols=["MSFT"],
            frequency="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 6, 30),
        )
        all_ds = builder.list_all()
        ids = {ds.dataset_id for ds in all_ds}
        assert uid1 in ids
        assert uid2 in ids

    def test_list_versions(self):
        """B3: list_versions returns all versions of a dataset."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.datasets.builder import DatasetBuilder

        uid = f"ver_test_{int(time.time() * 1000)}"
        builder = DatasetBuilder()
        builder.build_metadata_only(
            dataset_id=uid,
            name="Version Test 1",
            symbols=["AAPL"],
            frequency="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 6, 30),
        )
        builder.build_metadata_only(
            dataset_id=uid,
            name="Version Test 2",
            symbols=["AAPL", "MSFT"],
            frequency="1d",
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )
        versions = builder.list_versions(uid)
        assert len(versions) >= 2
        version_nums = {v.version for v in versions}
        assert "1.0.0" in version_nums
        assert "1.1.0" in version_nums
