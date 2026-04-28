from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from apps.auth import User, require_read, require_suggest
from apps.dto.api.data_sources import (
    DataSourceCapabilitiesResponse,
    DataSourceProfilesResponse,
    DataSourceTestRequest,
    DataSourceTestResponse,
    SaveDataSourceProfileResponse,
)
from core.data.source_registry import DEFAULT_PROFILE, DataSourceProfile, DataSourceRegistry

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])


@router.get("/profiles", response_model=DataSourceProfilesResponse)
async def list_profiles(user: User = Depends(require_read)) -> DataSourceProfilesResponse:
    registry = DataSourceRegistry()
    return DataSourceProfilesResponse(
        ok=True,
        default_profile_id=DEFAULT_PROFILE.profile_id,
        profiles=registry.list_profiles(),
    )


@router.post("/profiles", response_model=SaveDataSourceProfileResponse)
async def save_profile(
    profile: DataSourceProfile,
    user: User = Depends(require_suggest),
) -> SaveDataSourceProfileResponse:
    registry = DataSourceRegistry()
    try:
        saved = registry.save_profile(profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SaveDataSourceProfileResponse(ok=True, profile=saved)


@router.post("/test", response_model=DataSourceTestResponse)
async def test_provider(
    req: DataSourceTestRequest,
    user: User = Depends(require_read),
) -> DataSourceTestResponse:
    result = DataSourceRegistry().test_provider(req.provider_id, symbol=req.symbol)
    return DataSourceTestResponse(ok=result.ok, result=result)


@router.get("/capabilities", response_model=DataSourceCapabilitiesResponse)
async def list_capabilities(user: User = Depends(require_read)) -> DataSourceCapabilitiesResponse:
    return DataSourceCapabilitiesResponse(
        ok=True,
        capabilities=DataSourceRegistry().list_capabilities(),
    )
