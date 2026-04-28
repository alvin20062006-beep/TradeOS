"""Shared pytest configuration for backend tests."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class FakeModel:
    """Pickle-friendly model fixture for research adapter tests."""

    def __init__(self, predictions=None):
        self.predictions = predictions

    def predict(self, features):
        if self.predictions is not None:
            return self.predictions
        return [0.0 for _ in range(len(features))]


def pytest_collection_modifyitems(config, items):
    """Apply coarse test-layer markers without requiring every legacy file edit."""
    release_paths = {
        "tests/unit/test_desktop_runtime.py",
        "tests/unit/test_web_console_routes.py",
        "tests/integration/test_full_live_pipeline.py",
    }
    research_optional_names = {
        "test_backtest_research_pipeline.py",
        "test_portfolio_optimizer.py",
        "test_optimizer.py",
    }

    for item in items:
        rel_path = item.path.relative_to(project_root).as_posix()
        name = item.path.name

        if rel_path.startswith("tests/integration/"):
            item.add_marker(pytest.mark.integration)
        if name in research_optional_names:
            item.add_marker(pytest.mark.research_optional)
        if "legacy" in rel_path or "apps/console" in rel_path:
            item.add_marker(pytest.mark.legacy)
        if rel_path in release_paths:
            item.add_marker(pytest.mark.release)


@pytest.fixture(scope="session")
def project_root_path() -> Path:
    return project_root


@pytest.fixture
def mock_timestamp() -> datetime:
    return datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_market_bar(mock_timestamp):
    from core.schemas import MarketBar, TimeFrame

    return MarketBar(
        symbol="AAPL",
        timeframe=TimeFrame.M5,
        timestamp=mock_timestamp,
        open=185.50,
        high=186.00,
        low=185.25,
        close=185.75,
        volume=150000,
        quote_volume=27_862_500,
        trades=1500,
        vwap=185.68,
        source="yfinance",
    )


@pytest.fixture
def sample_order_book(mock_timestamp):
    from core.schemas import OrderBookSnapshot

    return OrderBookSnapshot(
        symbol="AAPL",
        timestamp=mock_timestamp,
        bids=[(185.75, 500), (185.74, 300), (185.73, 200)],
        asks=[(185.77, 400), (185.78, 250), (185.79, 300)],
        bid_depth=1000,
        ask_depth=950,
        spread=0.02,
        mid_price=185.76,
        imbalance=0.025,
    )


@pytest.fixture
def sample_engine_signal(mock_timestamp):
    from core.schemas import Direction, EngineSignal, Regime, TimeFrame

    return EngineSignal(
        engine_name="chan",
        symbol="AAPL",
        timestamp=mock_timestamp,
        timeframe=TimeFrame.M5,
        direction=Direction.LONG,
        confidence=0.75,
        regime=Regime.TRENDING_UP,
        entry_score=0.80,
        exit_score=0.40,
        entry_price=185.75,
        stop_price=184.50,
        target_price=190.00,
        risk_reward_ratio=2.5,
        pattern_type="chan_first_buy",
        pattern_name="chan_first_buy",
        module_scores={"fractal": 0.9, "stroke": 0.8, "zhongshu": 0.7},
        reasoning="chan first-buy signal with supporting structure",
        metadata={"level": 1},
    )


@pytest.fixture
def sample_arbitration_decision(mock_timestamp):
    from core.schemas import ArbitrationDecision, Direction, OrderType, Regime

    return ArbitrationDecision(
        decision_id=str(uuid4()),
        timestamp=mock_timestamp,
        symbol="AAPL",
        bias="long_bias",
        direction=Direction.LONG,
        confidence=0.78,
        regime=Regime.TRENDING_UP,
        entry_permission=True,
        no_trade_reason=None,
        max_position_pct=0.10,
        suggested_quantity=100,
        execution_style=OrderType.LIMIT,
        limit_price=185.75,
        stop_price=184.50,
        stop_logic={"type": "fixed", "price": 184.50},
        take_profit=190.00,
        engine_signals={
            "chan": 0.75,
            "technical": 0.70,
            "orderflow": 0.80,
            "sentiment": 0.65,
            "macro": 0.60,
        },
        consensus_score=0.72,
        reasoning="multi-engine agreement with chan confirmation",
        key_factors=["chan_signal", "technical_breakout", "low_volatility"],
        target_direction="LONG",
        target_quantity=100.0,
    )
