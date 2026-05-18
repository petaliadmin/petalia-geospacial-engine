from fastapi import APIRouter, Depends, HTTPException, status

from src.application.queries import (
    GetFieldAlertsQuery,
    GetFieldLatestQuery,
    GetFieldTimeseriesQuery,
)
from src.application.use_cases import (
    GetFieldAlertsUseCase,
    GetFieldLatestUseCase,
    GetFieldTimeseriesUseCase,
)
from src.infrastructure.cache.cache_service import RedisCacheService
from src.presentation.api.dependencies import (
    CacheDep,
    get_field_alerts_use_case,
    get_field_latest_use_case,
    get_field_timeseries_use_case,
)
from src.presentation.api.analyses import _dto_to_detail_response
from src.presentation.middlewares.auth_middleware import get_current_user
from src.presentation.schemas.analysis_schemas import (
    AlertResponse,
    AnalysisDetailResponse,
)
from src.presentation.schemas.field_schemas import (
    AlertListResponse,
    FieldTimeseriesResponse,
    TimeseriesEntryResponse,
    TileInfoResponse,
)
from src.shared.exceptions import FieldNotFoundException

router = APIRouter(prefix="/v1/fields", tags=["Fields"])


@router.get(
    "/{fieldId}/latest",
    response_model=AnalysisDetailResponse,
    summary="Get latest completed analysis for a field",
)
async def get_field_latest(
    fieldId: str,
    use_case: GetFieldLatestUseCase = Depends(get_field_latest_use_case),
    _user: dict = Depends(get_current_user),
) -> AnalysisDetailResponse:
    try:
        dto = await use_case.execute(GetFieldLatestQuery(field_id=fieldId))
        return _dto_to_detail_response(dto)
    except FieldNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.get(
    "/{fieldId}/timeseries",
    response_model=FieldTimeseriesResponse,
    summary="Get NDVI/NDWI timeseries for a field",
)
async def get_field_timeseries(
    fieldId: str,
    limit: int = 30,
    use_case: GetFieldTimeseriesUseCase = Depends(get_field_timeseries_use_case),
    _user: dict = Depends(get_current_user),
) -> FieldTimeseriesResponse:
    try:
        dto = await use_case.execute(GetFieldTimeseriesQuery(field_id=fieldId, limit=limit))
        return FieldTimeseriesResponse(
            fieldId=dto.field_id,
            total=dto.total,
            entries=[
                TimeseriesEntryResponse(
                    analysisId=e.analysis_id,
                    analysisDate=e.analysis_date,
                    ndviMean=e.ndvi_mean,
                    ndwiMean=e.ndwi_mean,
                    cloudCoverage=e.cloud_coverage,
                    trend=e.trend,
                    health=e.health,
                )
                for e in dto.entries
            ],
        )
    except FieldNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.get(
    "/{fieldId}/tiles",
    response_model=TileInfoResponse,
    summary="Get tile map URL for a field",
)
async def get_field_tiles(
    fieldId: str,
    cache: CacheDep,
    _user: dict = Depends(get_current_user),
) -> TileInfoResponse:
    tile_url = await cache.get_tiles(fieldId)
    thumbnail_url = await cache.get_thumbnail(fieldId)
    if not tile_url and not thumbnail_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tiles available for field '{fieldId}'. Run an analysis first.",
        )
    return TileInfoResponse(
        fieldId=fieldId,
        tileUrl=tile_url,
        thumbnailUrl=thumbnail_url,
    )


@router.get(
    "/{fieldId}/thumbnail",
    response_model=TileInfoResponse,
    summary="Get thumbnail PNG URL for a field",
)
async def get_field_thumbnail(
    fieldId: str,
    cache: CacheDep,
    _user: dict = Depends(get_current_user),
) -> TileInfoResponse:
    thumbnail_url = await cache.get_thumbnail(fieldId)
    if not thumbnail_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No thumbnail available for field '{fieldId}'. Run an analysis first.",
        )
    return TileInfoResponse(fieldId=fieldId, thumbnailUrl=thumbnail_url)


@router.get(
    "/{fieldId}/alerts",
    response_model=AlertListResponse,
    summary="Get agronomic alerts for a field",
)
async def get_field_alerts(
    fieldId: str,
    limit: int = 50,
    offset: int = 0,
    use_case: GetFieldAlertsUseCase = Depends(get_field_alerts_use_case),
    _user: dict = Depends(get_current_user),
) -> AlertListResponse:
    try:
        alerts = await use_case.execute(
            GetFieldAlertsQuery(field_id=fieldId, limit=limit, offset=offset)
        )
        return AlertListResponse(
            fieldId=fieldId,
            total=len(alerts),
            alerts=[
                {
                    "id": a.id,
                    "severity": a.severity,
                    "alertType": a.alert_type,
                    "message": a.message,
                    "createdAt": a.created_at.isoformat(),
                }
                for a in alerts
            ],
        )
    except FieldNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
