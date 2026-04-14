from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LiveRunRequest(BaseModel):
    """Shared request for live analysis / live pipeline."""

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="1d", description="1m | 5m | 15m | 30m | 1h | 4h | 1d | 1w")
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


class LiveDataSummaryView(BaseModel):
    symbol: str
    timeframe: str
    lookback: int
    start: datetime
    end: datetime
    bar_count: int
    intraday_bar_count: int
    latest_timestamp: datetime


class LiveModuleView(BaseModel):
    module: str
    status: str
    provider: str
    adapter: str
    real_coverage: str
    placeholder_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


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
    audit: dict
    feedback: dict
