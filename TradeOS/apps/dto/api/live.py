from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class LiveRunRequest(BaseModel):
    """Shared request for live analysis / live pipeline."""

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="1d", description="1m | 5m | 15m | 30m | 1h | 4h | 1d | 1w")
    market_type: str = Field(default="auto", description="auto | equity | commodity | crypto | fx | index")
    profile_id: str = Field(default="default-live", min_length=1, max_length=64)
    lookback: int = Field(default=180, ge=30, le=1000)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    news_limit: int = Field(default=10, ge=1, le=30)

    @field_validator("timeframe")
    @classmethod
    def normalize_timeframe(cls, value: str) -> str:
        value = value.lower().strip()
        allowed = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}
        if value not in allowed:
            raise ValueError(f"timeframe must be one of {sorted(allowed)}")
        return value

    @field_validator("market_type")
    @classmethod
    def normalize_market_type(cls, value: str) -> str:
        value = value.lower().strip()
        allowed = {"auto", "equity", "commodity", "crypto", "fx", "index"}
        if value not in allowed:
            raise ValueError(f"market_type must be one of {sorted(allowed)}")
        return value


class LiveDataSummaryView(BaseModel):
    symbol: str
    timeframe: str
    market_type: str = "auto"
    profile_id: str = "default-live"
    lookback: int
    start: datetime
    end: datetime
    bar_count: int
    intraday_bar_count: int
    latest_timestamp: datetime


class LiveModuleView(BaseModel):
    module: str
    status: str
    coverage_status: str
    provider: str
    adapter: str
    real_coverage: str
    input_data: list[str] = Field(default_factory=list)
    latest_data_time: Optional[datetime] = None
    data_count: Optional[int] = None
    output_direction: str = "n/a"
    confidence: Optional[float] = None
    placeholder_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    raw_response: Any = None


class LiveAnalysisResponse(BaseModel):
    ok: bool
    data: LiveDataSummaryView
    modules: list[LiveModuleView]
    signal_summary: dict


class LivePipelineResponse(BaseModel):
    ok: bool
    data: LiveDataSummaryView
    modules: list[LiveModuleView]
    decision: dict
    plan: dict
    suggestions: list[dict] = Field(default_factory=list)
    explanation: dict = Field(default_factory=dict)
    watch_plan: dict = Field(default_factory=dict)
    data_status: dict = Field(default_factory=dict)
    execution: dict = Field(default_factory=dict)
    audit: dict
    feedback: dict
