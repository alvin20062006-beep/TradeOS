"""Data source profile registry for live TradeOS pipelines.

Profiles select provider IDs for each external-data lane. Capabilities make the
REAL / PROXY / PLACEHOLDER / UNAVAILABLE boundary explicit so product surfaces
do not accidentally present reserved integrations as completed providers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProviderCapabilityStatus(StrEnum):
    REAL = "REAL"
    PROXY = "PROXY"
    PLACEHOLDER = "PLACEHOLDER"
    UNAVAILABLE = "UNAVAILABLE"


class ProviderCapability(BaseModel):
    provider_id: str
    category: str
    display_name: str
    provider: str
    adapter: str
    status: ProviderCapabilityStatus
    testable: bool = True
    notes: list[str] = Field(default_factory=list)


class DataSourceProfile(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)
    market_provider: str = "yahoo_market"
    fundamental_provider: str = "yahoo_fundamentals"
    macro_provider: str = "fred_macro"
    news_provider: str = "yahoo_news"
    orderflow_provider: str = "intraday_bars_proxy"
    sentiment_provider: str = "news_sentiment"
    execution_provider: str = "simulation_execution"
    enabled: bool = True
    notes: str = ""


class ProviderTestResult(BaseModel):
    provider_id: str
    status: ProviderCapabilityStatus
    ok: bool
    tested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


CAPABILITIES: dict[str, ProviderCapability] = {
    "yahoo_market": ProviderCapability(
        provider_id="yahoo_market",
        category="market",
        display_name="Yahoo Market",
        provider="Yahoo Finance",
        adapter="YahooMarketAdapter",
        status=ProviderCapabilityStatus.REAL,
        notes=["Real OHLCV bars via yfinance."],
    ),
    "csv_local": ProviderCapability(
        provider_id="csv_local",
        category="market",
        display_name="CSV Local",
        provider="Local CSV",
        adapter="CSVProvider",
        status=ProviderCapabilityStatus.REAL,
        notes=["Real local files when CSV data is configured under .runtime/data_sources/csv."],
    ),
    "trading_terminal_api": ProviderCapability(
        provider_id="trading_terminal_api",
        category="market",
        display_name="Trading Software API",
        provider="Reserved trading terminal",
        adapter="PLACEHOLDER",
        status=ProviderCapabilityStatus.PLACEHOLDER,
        testable=False,
        notes=["Reserved integration point. No live terminal adapter is active."],
    ),
    "yahoo_fundamentals": ProviderCapability(
        provider_id="yahoo_fundamentals",
        category="fundamental",
        display_name="Yahoo Fundamentals",
        provider="Yahoo Finance",
        adapter="YahooFundamentalAdapter",
        status=ProviderCapabilityStatus.REAL,
        notes=["Real fundamentals snapshot; some ratio fields remain provider-limited."],
    ),
    "fred_macro": ProviderCapability(
        provider_id="fred_macro",
        category="macro",
        display_name="FRED Macro",
        provider="FRED public CSV",
        adapter="FredMacroAdapter",
        status=ProviderCapabilityStatus.REAL,
        notes=["Real public FRED indicators for macro regime context."],
    ),
    "macro_news": ProviderCapability(
        provider_id="macro_news",
        category="macro",
        display_name="Macro News",
        provider="Yahoo macro tickers",
        adapter="FredMacroAdapterNews",
        status=ProviderCapabilityStatus.PROXY,
        notes=["Macro news is converted to MacroEvent with missing forecast/actual fields flagged."],
    ),
    "yahoo_news": ProviderCapability(
        provider_id="yahoo_news",
        category="news",
        display_name="Yahoo News",
        provider="Yahoo Finance",
        adapter="YahooNewsAdapter",
        status=ProviderCapabilityStatus.REAL,
        notes=["Real Yahoo Finance news items; sentiment score may be derived by adapter keywords."],
    ),
    "rss_news": ProviderCapability(
        provider_id="rss_news",
        category="news",
        display_name="RSS News",
        provider="Reserved RSS",
        adapter="PLACEHOLDER",
        status=ProviderCapabilityStatus.PLACEHOLDER,
        testable=False,
        notes=["Reserved RSS adapter; not active in the current backend."],
    ),
    "intraday_bars_proxy": ProviderCapability(
        provider_id="intraday_bars_proxy",
        category="orderflow",
        display_name="Intraday Bars Proxy",
        provider="Yahoo intraday bars",
        adapter="OrderFlowEngine bars proxy",
        status=ProviderCapabilityStatus.PROXY,
        notes=["Uses real 1m bars as a proxy because trade prints/depth are unavailable."],
    ),
    "trade_prints": ProviderCapability(
        provider_id="trade_prints",
        category="orderflow",
        display_name="Trade Prints",
        provider="Reserved broker/trading terminal",
        adapter="PLACEHOLDER",
        status=ProviderCapabilityStatus.PLACEHOLDER,
        testable=False,
        notes=["Reserved tick/trade-print path. No active provider yet."],
    ),
    "level2_orderbook": ProviderCapability(
        provider_id="level2_orderbook",
        category="orderflow",
        display_name="Level2 OrderBook",
        provider="Reserved Level2 feed",
        adapter="PLACEHOLDER",
        status=ProviderCapabilityStatus.PLACEHOLDER,
        testable=False,
        notes=["Reserved depth-of-book path. Not available in the local product build."],
    ),
    "news_sentiment": ProviderCapability(
        provider_id="news_sentiment",
        category="sentiment",
        display_name="News Sentiment",
        provider="Yahoo News + OHLCV",
        adapter="SentimentEngine",
        status=ProviderCapabilityStatus.PROXY,
        notes=["Real news headlines plus market context; social/forum/analyst fields remain flagged."],
    ),
    "social_sentiment": ProviderCapability(
        provider_id="social_sentiment",
        category="sentiment",
        display_name="Social Sentiment",
        provider="Reserved social source",
        adapter="PLACEHOLDER",
        status=ProviderCapabilityStatus.PLACEHOLDER,
        testable=False,
        notes=["Reserved social source. No active social data provider."],
    ),
    "funding_oi_liquidation": ProviderCapability(
        provider_id="funding_oi_liquidation",
        category="sentiment",
        display_name="Funding / OI / Liquidation",
        provider="Reserved derivatives data",
        adapter="PLACEHOLDER",
        status=ProviderCapabilityStatus.PLACEHOLDER,
        testable=False,
        notes=["Reserved derivatives sentiment path. Current engine uses explicit proxy estimates only."],
    ),
    "simulation_execution": ProviderCapability(
        provider_id="simulation_execution",
        category="execution",
        display_name="Simulation Execution",
        provider="Local simulation runtime",
        adapter="ExecutionRuntime(SIMULATION)",
        status=ProviderCapabilityStatus.REAL,
        notes=["Local deterministic simulation execution. Does not place live orders."],
    ),
    "paper_execution": ProviderCapability(
        provider_id="paper_execution",
        category="execution",
        display_name="Paper Execution",
        provider="Reserved broker paper account",
        adapter="PLACEHOLDER",
        status=ProviderCapabilityStatus.PLACEHOLDER,
        testable=False,
        notes=["Reserved broker paper trading adapter. Not active."],
    ),
    "live_broker": ProviderCapability(
        provider_id="live_broker",
        category="execution",
        display_name="Live Broker",
        provider="Reserved broker API",
        adapter="PLACEHOLDER",
        status=ProviderCapabilityStatus.PLACEHOLDER,
        testable=False,
        notes=["Reserved live broker adapter. Default product never sends live orders."],
    ),
}


DEFAULT_PROFILE = DataSourceProfile(
    profile_id="default-live",
    market_provider="yahoo_market",
    fundamental_provider="yahoo_fundamentals",
    macro_provider="fred_macro",
    news_provider="yahoo_news",
    orderflow_provider="intraday_bars_proxy",
    sentiment_provider="news_sentiment",
    execution_provider="simulation_execution",
    enabled=True,
    notes="Default local profile: Yahoo/FRED real data plus explicit orderflow/sentiment proxy boundaries.",
)


class DataSourceRegistry:
    """Runtime registry and local profile store."""

    def __init__(self, store_path: Optional[Path] = None) -> None:
        self.store_path = store_path or self._default_store_path()

    @staticmethod
    def _default_store_path() -> Path:
        try:
            from infra.config.settings import get_settings

            base = get_settings().app_data_dir / "data_sources"
        except Exception:
            base = Path(__file__).resolve().parents[2] / ".runtime" / "data_sources"
        base.mkdir(parents=True, exist_ok=True)
        return base / "profiles.json"

    def list_capabilities(self) -> list[ProviderCapability]:
        return sorted(CAPABILITIES.values(), key=lambda item: (item.category, item.provider_id))

    def get_capability(self, provider_id: str) -> ProviderCapability:
        if provider_id not in CAPABILITIES:
            return ProviderCapability(
                provider_id=provider_id,
                category="unknown",
                display_name=provider_id,
                provider="unknown",
                adapter="UNAVAILABLE",
                status=ProviderCapabilityStatus.UNAVAILABLE,
                testable=False,
                notes=["Provider ID is not registered."],
            )
        return CAPABILITIES[provider_id]

    def list_profiles(self) -> list[DataSourceProfile]:
        profiles = {DEFAULT_PROFILE.profile_id: DEFAULT_PROFILE}
        for profile in self._read_profiles():
            profiles[profile.profile_id] = profile
        return list(profiles.values())

    def get_profile(self, profile_id: Optional[str] = None) -> DataSourceProfile:
        wanted = profile_id or DEFAULT_PROFILE.profile_id
        for profile in self.list_profiles():
            if profile.profile_id == wanted:
                return profile
        raise KeyError(f"Data source profile not found: {wanted}")

    def save_profile(self, profile: DataSourceProfile) -> DataSourceProfile:
        self._validate_profile(profile)
        profiles = {item.profile_id: item for item in self._read_profiles()}
        profiles[profile.profile_id] = profile
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps([item.model_dump() for item in profiles.values()], indent=2, default=str),
            encoding="utf-8",
        )
        return profile

    def test_provider(self, provider_id: str, symbol: str = "AAPL") -> ProviderTestResult:
        cap = self.get_capability(provider_id)
        if cap.status in {ProviderCapabilityStatus.PLACEHOLDER, ProviderCapabilityStatus.UNAVAILABLE}:
            return ProviderTestResult(
                provider_id=provider_id,
                status=cap.status,
                ok=False,
                message=f"{cap.display_name} is {cap.status.value}; no real connection is active.",
                detail={"notes": cap.notes},
            )
        try:
            detail = self._run_provider_test(provider_id, symbol)
            return ProviderTestResult(
                provider_id=provider_id,
                status=cap.status,
                ok=True,
                message=f"{cap.display_name} connection test succeeded.",
                detail=detail,
            )
        except Exception as exc:
            return ProviderTestResult(
                provider_id=provider_id,
                status=ProviderCapabilityStatus.UNAVAILABLE,
                ok=False,
                message=f"{cap.display_name} connection test failed.",
                detail={"error": str(exc), "notes": cap.notes},
            )

    def _read_profiles(self) -> list[DataSourceProfile]:
        if not self.store_path.exists():
            return []
        raw = json.loads(self.store_path.read_text(encoding="utf-8") or "[]")
        return [DataSourceProfile(**item) for item in raw]

    def _validate_profile(self, profile: DataSourceProfile) -> None:
        provider_ids = [
            profile.market_provider,
            profile.fundamental_provider,
            profile.macro_provider,
            profile.news_provider,
            profile.orderflow_provider,
            profile.sentiment_provider,
            profile.execution_provider,
        ]
        unknown = [provider_id for provider_id in provider_ids if provider_id not in CAPABILITIES]
        if unknown:
            raise ValueError(f"Unknown provider IDs: {', '.join(unknown)}")

    def _run_provider_test(self, provider_id: str, symbol: str) -> dict[str, Any]:
        if provider_id in {"yahoo_market", "intraday_bars_proxy"}:
            from core.data.live.providers import YahooFinanceLiveProvider

            end = datetime.now(UTC)
            result = YahooFinanceLiveProvider().fetch_bars(
                symbol=symbol,
                interval="1d",
                start=end - timedelta(days=14),
                end=end,
            )
            return {"rows": len(result.payload), "provider": result.provider}

        if provider_id == "yahoo_fundamentals":
            from core.data.live.providers import YahooFinanceLiveProvider

            result = YahooFinanceLiveProvider().fetch_fundamentals(symbol=symbol)
            return {"fields": len(result.payload), "provider": result.provider}

        if provider_id in {"yahoo_news", "news_sentiment", "macro_news"}:
            from core.data.live.providers import YahooFinanceLiveProvider

            result = YahooFinanceLiveProvider().fetch_news(symbol=symbol, limit=5)
            return {"items": len(result.payload), "provider": result.provider}

        if provider_id == "fred_macro":
            from core.data.live.providers import FredMacroProvider

            result = FredMacroProvider().fetch_indicator("DFF", lookback_rows=2)
            return {"rows": len(result.payload), "provider": result.provider, "series": "DFF"}

        if provider_id == "csv_local":
            csv_dir = self.store_path.parent / "csv"
            files = list(csv_dir.glob("*.csv")) if csv_dir.exists() else []
            if not files:
                raise FileNotFoundError(f"No CSV files found under {csv_dir}")
            return {"files": [str(path.name) for path in files[:5]], "provider": "csv_local"}

        if provider_id == "simulation_execution":
            return {"mode": "simulation", "provider": "local"}

        raise ValueError(f"No connection test implemented for {provider_id}")
