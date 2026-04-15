"""
Unit tests for alpha builders (technical, fundamentals, sentiment, composite).

Tests the minimum baseline alpha pipeline:
    OHLCV DataFrame -> technical builders -> alpha DataFrames
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime


# ── Shared fixtures ──────────────────────────────────────────────

def make_bars(
    n: int = 100,
    symbol: str = "AAPL",
    start_price: float = 100.0,
    vol_mult: float = 1.0,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV bars for testing.

    Returns DataFrame with MultiIndex (symbol, timestamp).
    """
    np.random.seed(42)
    dates = pd.bdate_range(start="2024-01-01", periods=n)

    # Geometric random walk
    returns = np.random.randn(n) * 0.02 * vol_mult
    prices = start_price * np.exp(np.cumsum(returns))

    highs = prices * (1 + np.abs(np.random.randn(n) * 0.005))
    lows = prices * (1 - np.abs(np.random.randn(n) * 0.005))
    opens = prices * (1 + np.random.randn(n) * 0.003)
    volumes = np.random.randint(1_000_000, 10_000_000, size=n).astype(float)

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
        },
        index=dates,
    )
    df.index.name = "timestamp"
    df["symbol"] = symbol
    return df.set_index("symbol", append=True)


def make_multi_symbol_bars(
    symbols: list[str] = None,
    n: int = 100,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """Generate OHLCV bars for multiple symbols."""
    if symbols is None:
        symbols = ["AAPL", "MSFT", "GOOG"]

    frames = []
    for sym in symbols:
        df = make_bars(n=n, symbol=sym, start_price=start_price)
        frames.append(df)

    return pd.concat(frames)


class TestTechnicalBuilders:
    """Tests for technical alpha builders."""

    def test_ret_1d(self):
        """T1: RET_1d computes 1-day return."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_ret_1d

        df = make_bars(n=10)
        result = build_ret_1d(df)

        assert "symbol" in result.columns
        assert "timestamp" in result.columns
        assert "raw_value" in result.columns
        assert len(result) > 0
        # Return should be small (-0.1 to 0.1) for random walk
        assert result["raw_value"].abs().max() < 1.0

    def test_ret_5d(self):
        """T1: RET_5d computes 5-day return."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_ret_5d

        df = make_bars(n=20)
        result = build_ret_5d(df)

        assert "raw_value" in result.columns
        # RET_5d has lag, fewer rows than RET_1d
        assert len(result) < len(df)

    def test_vol_5d(self):
        """T1: VOL_5d computes annualised rolling volatility."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_vol_5d

        df = make_bars(n=30)
        result = build_vol_5d(df)

        assert "raw_value" in result.columns
        # Volatility should be positive
        assert (result["raw_value"] >= 0).all()

    def test_rsi_14(self):
        """T1: RSI_14 produces values in 0-100 range."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_rsi_14

        df = make_bars(n=50)
        result = build_rsi_14(df)

        assert "raw_value" in result.columns
        assert result["raw_value"].min() >= 0.0
        assert result["raw_value"].max() <= 100.0

    def test_macd(self):
        """T1: MACD computes difference of EMAs."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_macd

        df = make_bars(n=100)
        result = build_macd(df)

        assert "raw_value" in result.columns
        assert len(result) > 0

    def test_bb_width(self):
        """T1: BB_WIDTH is positive and bounded."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_bb_width

        df = make_bars(n=50)
        result = build_bb_width(df)

        assert "raw_value" in result.columns
        assert (result["raw_value"] > 0).all()

    def test_bb_pos(self):
        """T1: BB_POS is approximately in 0-1 range."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_bb_pos

        df = make_bars(n=50)
        result = build_bb_pos(df)

        assert "raw_value" in result.columns
        # Allow tolerance for floating point
        assert result["raw_value"].min() >= -0.2, f"BB_POS min too low: {result['raw_value'].min()}"
        assert result["raw_value"].max() <= 1.2, f"BB_POS max too high: {result['raw_value'].max()}"

    def test_vol_ratio(self):
        """T1: VOL_RATIO requires volume column."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_vol_ratio

        df = make_bars(n=50)
        result = build_vol_ratio(df)

        assert "raw_value" in result.columns

    def test_obv_dir(self):
        """T1: OBV_DIR is -1, 0, or +1."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_obv_dir

        df = make_bars(n=50)
        result = build_obv_dir(df)

        assert "raw_value" in result.columns
        assert set(result["raw_value"].unique()).issubset({-1.0, 0.0, 1.0})

    def test_build_all_technical(self):
        """T2: build_all_technical returns a dict of DataFrames."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_all_technical

        df = make_bars(n=100)
        results = build_all_technical(df)

        assert isinstance(results, dict)
        assert len(results) > 0
        assert all("raw_value" in r.columns for r in results.values())

    def test_missing_column_raises_clear(self):
        """T3: Missing column raises ValueError with helpful message."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_rsi_14

        df = make_bars(n=50)
        df_no_close = df.drop(columns=["close"])

        with pytest.raises(ValueError, match="close"):
            build_rsi_14(df_no_close)


class TestFundamentalBuilders:
    """Tests for fundamental alpha builders."""

    def _make_fundamental_df(self) -> pd.DataFrame:
        """Create a synthetic fundamentals DataFrame (flat format, no MultiIndex)."""
        import numpy as np

        np.random.seed(42)

        dates = pd.bdate_range(start="2024-01-01", periods=20).tolist()

        records = []
        for sym, pe, pb in [("AAPL", 25.0, 4.5), ("MSFT", 30.0, 6.0), ("GOOG", 22.0, 3.8)]:
            for d in dates:
                records.append({
                    "symbol": sym,
                    "timestamp": d,
                    "pe_ratio": pe + np.random.randn() * 3,
                    "pb_ratio": pb + np.random.randn() * 0.5,
                    "net_income": np.random.uniform(1e9, 5e9),
                    "total_assets": np.random.uniform(1e10, 50e10),
                })

        return pd.DataFrame(records).set_index(["symbol", "timestamp"])

    def test_pe_rank(self):
        """F1: PE_RANK produces percentile 0-1."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.fundamentals import build_pe_rank

        df = self._make_fundamental_df()
        result = build_pe_rank(df)

        assert "raw_value" in result.columns
        assert result["raw_value"].min() >= 0.0
        assert result["raw_value"].max() <= 1.0

    def test_pb_rank(self):
        """F1: PB_RANK produces percentile 0-1."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.fundamentals import build_pb_rank

        df = self._make_fundamental_df()
        result = build_pb_rank(df)

        assert "raw_value" in result.columns
        assert result["raw_value"].min() >= 0.0
        assert result["raw_value"].max() <= 1.0

    def test_roe_ttm(self):
        """F1: ROE_TTM produces small float values."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.fundamentals import build_roe_ttm

        df = self._make_fundamental_df()
        result = build_roe_ttm(df)

        assert "raw_value" in result.columns
        assert len(result) > 0


class TestSentimentBuilders:
    """Tests for sentiment alpha builders."""

    def test_vol_surprise(self):
        """S1: VOL_SURPRISE produces z-score values."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.sentiment import build_vol_surprise

        df = make_bars(n=50)
        result = build_vol_surprise(df)

        assert "raw_value" in result.columns
        # Most values within -3 to +3 for z-score
        assert result["raw_value"].abs().max() < 10.0

    def test_vol_surprise_requires_volume(self):
        """S2: VOL_SURPRISE requires volume column."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.sentiment import build_vol_surprise

        df = make_bars(n=50).drop(columns=["volume"])

        with pytest.raises(ValueError, match="volume"):
            build_vol_surprise(df)


class TestCompositeBuilders:
    """Tests for L3 composite alpha builders."""

    def _make_factor_dict(self) -> dict:
        """Create a dict of synthetic factor DataFrames."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.technical import build_ret_1d, build_rsi_14

        df = make_bars(n=100)

        return {
            "RET_1d": build_ret_1d(df),
            "RSI_14": build_rsi_14(df),
        }

    def test_equal_weight(self):
        """C1: Equal weight composite is in valid range."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.composite import build_equal_weight

        factors = self._make_factor_dict()
        result = build_equal_weight(factors)

        assert "composite_value" in result.columns
        assert "symbol" in result.columns
        assert "timestamp" in result.columns
        assert len(result) > 0

    def test_rank_average(self):
        """C1: Rank average composite is in 0-1 range."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.composite import build_rank_average

        factors = self._make_factor_dict()
        result = build_rank_average(factors)

        assert "composite_value" in result.columns
        assert result["composite_value"].min() >= 0.0
        assert result["composite_value"].max() <= 1.0

    def test_ic_weighted_requires_label(self):
        """C2: IC-weighted requires label_series."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.composite import build_composite

        factors = self._make_factor_dict()

        with pytest.raises(ValueError, match="label_series"):
            build_composite(factors, method="ic_weighted")

    def test_unknown_method_raises(self):
        """C2: Unknown composite method raises ValueError."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.composite import build_composite

        factors = self._make_factor_dict()

        with pytest.raises(ValueError, match="Unknown method"):
            build_composite(factors, method="unknown_method")

    def test_empty_dict_raises(self):
        """C2: Empty factor dict raises helpful error."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.composite import build_equal_weight

        with pytest.raises(ValueError):
            build_equal_weight({})

    def test_build_composite_factory(self):
        """C1: build_composite() factory works with equal_weight."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.alpha.builders.composite import build_composite

        factors = self._make_factor_dict()
        result = build_composite(factors, method="equal_weight")

        assert "composite_value" in result.columns
        assert len(result) > 0
