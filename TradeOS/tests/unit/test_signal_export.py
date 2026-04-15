"""
Unit tests for signal export.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import tempfile
import json

from core.research.models import SignalCandidate
from core.research.deployment.signal_export import (
    SignalExportConfig,
    SignalExporter,
    export_signals,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_signals():
    """Sample SignalCandidate list."""
    signals = []
    for i, sym in enumerate(["AAPL", "MSFT", "GOOGL", "AMZN", "META"]):
        sig = SignalCandidate(
            candidate_id=f"sig_{i:03d}",
            experiment_id="exp_test_001",
            model_artifact_id="art_test_001",
            symbol=sym,
            timestamp=datetime(2024, 1, 15),
            score=0.5 - i * 0.1,
            score_normalized=0.5 - i * 0.1,
            direction_hint="long" if i < 3 else "short",
            confidence=0.8 - i * 0.1,
            horizon=1,
            metadata={"rank": i + 1},
        )
        signals.append(sig)
    return signals


# ── Config Tests ────────────────────────────────────────────────────────────


class TestSignalExportConfig:
    def test_default_config(self):
        config = SignalExportConfig()
        assert config.format == "json"
        assert config.include_metadata is True
        assert config.top_k is None
        assert config.score_threshold is None

    def test_custom_config(self):
        config = SignalExportConfig(
            format="csv",
            top_k=10,
            score_threshold=0.2,
        )
        assert config.format == "csv"
        assert config.top_k == 10
        assert config.score_threshold == 0.2


# ── Exporter Tests ───────────────────────────────────────────────────────────


class TestSignalExporter:
    def test_export_json(self, sample_signals):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SignalExportConfig(
                format="json",
                output_dir=tmpdir,
            )
            exporter = SignalExporter(config)
            path = exporter.export(sample_signals, "exp_test_001")

            assert path.exists()
            assert path.suffix == ".json"

            # Verify content
            with open(path) as f:
                data = json.load(f)
            assert data["experiment_id"] == "exp_test_001"
            assert data["n_signals"] == 5

    def test_export_csv(self, sample_signals):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SignalExportConfig(
                format="csv",
                output_dir=tmpdir,
            )
            exporter = SignalExporter(config)
            path = exporter.export(sample_signals, "exp_test_001")

            assert path.exists()
            assert path.suffix == ".csv"

            # Verify content
            df = pd.read_csv(path)
            assert len(df) == 5
            assert "symbol" in df.columns
            assert "score" in df.columns

    def test_export_with_top_k(self, sample_signals):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SignalExportConfig(
                format="json",
                output_dir=tmpdir,
                top_k=3,
            )
            exporter = SignalExporter(config)
            path = exporter.export(sample_signals, "exp_test_001")

            with open(path) as f:
                data = json.load(f)
            assert data["n_signals"] == 3

    def test_export_with_score_threshold(self, sample_signals):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SignalExportConfig(
                format="json",
                output_dir=tmpdir,
                score_threshold=0.3,  # Only |score| >= 0.3
            )
            exporter = SignalExporter(config)
            path = exporter.export(sample_signals, "exp_test_001")

            with open(path) as f:
                data = json.load(f)
            # AAPL (0.5), MSFT (0.4), GOOGL (0.3) should pass
            # AMZN (0.2) and META (0.1) should be filtered
            assert data["n_signals"] == 3

    def test_export_without_metadata(self, sample_signals):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SignalExportConfig(
                format="json",
                output_dir=tmpdir,
                include_metadata=False,
            )
            exporter = SignalExporter(config)
            path = exporter.export(sample_signals, "exp_test_001")

            with open(path) as f:
                data = json.load(f)
            # Metadata should be None
            for sig in data["signals"]:
                assert sig.get("metadata") is None

    def test_to_dataframe(self, sample_signals):
        config = SignalExportConfig()
        exporter = SignalExporter(config)
        df = exporter.to_dataframe(sample_signals)

        assert len(df) == 5
        assert "symbol" in df.columns
        assert "score" in df.columns

    def test_c4_constraint_violation(self):
        """Test that execution-layer fields raise error."""
        # Create a signal with execution-layer field in metadata
        sig = SignalCandidate(
            candidate_id="sig_bad",
            experiment_id="exp_test",
            model_artifact_id="art_test",
            symbol="AAPL",
            timestamp=datetime(2024, 1, 15),
            score=0.5,
            score_normalized=0.5,
            direction_hint="long",
            confidence=0.8,
            horizon=1,
            metadata={"order_type": "limit"},  # Execution-layer field!
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config = SignalExportConfig(output_dir=tmpdir)
            exporter = SignalExporter(config)

            with pytest.raises(ValueError, match="C4 constraint"):
                exporter.export([sig], "exp_test")

    def test_convenience_function(self, sample_signals):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_signals(
                sample_signals,
                "exp_test_001",
                format="json",
                output_dir=tmpdir,
                top_k=3,
            )
            assert path.exists()
