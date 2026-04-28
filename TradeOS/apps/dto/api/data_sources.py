from __future__ import annotations

from pydantic import BaseModel, Field

from core.data.source_registry import (
    DataSourceProfile,
    ProviderCapability,
    ProviderTestResult,
)


class DataSourceProfilesResponse(BaseModel):
    ok: bool
    default_profile_id: str
    profiles: list[DataSourceProfile]


class SaveDataSourceProfileResponse(BaseModel):
    ok: bool
    profile: DataSourceProfile


class DataSourceTestRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=96)
    symbol: str = Field(default="AAPL", min_length=1, max_length=32)


class DataSourceTestResponse(BaseModel):
    ok: bool
    result: ProviderTestResult


class DataSourceCapabilitiesResponse(BaseModel):
    ok: bool
    capabilities: list[ProviderCapability]
