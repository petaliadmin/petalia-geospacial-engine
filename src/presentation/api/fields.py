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
from src.presentation.api.analyses import _dto_to_detail_response
from src.presentation.api.dependencies import (
    CacheDep,
    get_field_alerts_use_case,
    get_field_latest_use_case,
    get_field_timeseries_use_case,
)
from src.presentation.middlewares.auth_middleware import get_current_user
from src.presentation.schemas.analysis_schemas import AnalysisDetailResponse
from src.presentation.schemas.field_schemas import (
    AlertListResponse,
    FieldTimeseriesResponse,
    TileInfoResponse,
    TimeseriesEntryResponse,
)
from src.shared.exceptions import FieldNotFoundException

router = APIRouter(prefix="/v1/fields", tags=["Fields"])


@router.get(
    "/{field_id}/latest",
    response_model=AnalysisDetailResponse,
    summary="Get latest completed analysis for a field",
)
async def get_field_latest(
    field_id: str,
    use_case: GetFieldLatestUseCase = Depends(get_field_latest_use_case),
    _user: dict = Depends(get_current_user),
) -> AnalysisDetailResponse:
    try:
        dto = await use_case.execute(GetFieldLatestQuery(field_id=field_id))
        return _dto_to_detail_response(dto)
    except FieldNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.get(
    "/{field_id}/timeseries",
    response_model=FieldTimeseriesResponse,
    summary="Get vegetation index timeseries for a field (NDVI, NDMI, NDRE, SAVI, EVI2)",
)
async def get_field_timeseries(
    field_id: str,
    limit: int = 30,
    use_case: GetFieldTimeseriesUseCase = Depends(get_field_timeseries_use_case),
    _user: dict = Depends(get_current_user),
) -> FieldTimeseriesResponse:
    try:
        dto = await use_case.execute(GetFieldTimeseriesQuery(field_id=field_id, limit=limit))
        return FieldTimeseriesResponse(
            fieldId=dto.field_id,  # noqa: N815
            total=dto.total,
            entries=[
                TimeseriesEntryResponse(
                    analysisId=e.analysis_id,  # noqa: N815
                    analysisDate=e.analysis_date,  # noqa: N815
                    ndviMean=e.ndvi_mean,  # noqa: N815
                    ndmiMean=e.ndmi_mean,  # noqa: N815  S1-3: was ndwiMean
                    ndreMean=e.ndre_mean,  # noqa: N815  S4-3
                    saviMean=e.savi_mean,  # noqa: N815  S4-3
                    evi2Mean=e.evi2_mean,  # noqa: N815  S4-3
                    cloudCoverage=e.cloud_coverage,  # noqa: N815
                    trend=e.trend,
                    health=e.health,
                )
                for e in dto.entries
            ],
        )
    except FieldNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.get(
    "/{field_id}/tiles",
    response_model=TileInfoResponse,
    summary="Get tile map URL for a field",
)
async def get_field_tiles(
    field_id: str,
    cache: CacheDep,
    _user: dict = Depends(get_current_user),
) -> TileInfoResponse:
    tile_url = await cache.get_tiles(field_id)
    thumbnail_url = await cache.get_thumbnail(field_id)
    if not tile_url and not thumbnail_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tiles available for field '{field_id}'. Run an analysis first.",
        )
    return TileInfoResponse(
        fieldId=field_id,  # noqa: N815
        tileUrl=tile_url,  # noqa: N815
        thumbnailUrl=thumbnail_url,  # noqa: N815
    )


@router.get(
    "/{field_id}/thumbnail",
    response_model=TileInfoResponse,
    summary="Get thumbnail PNG URL for a field",
)
async def get_field_thumbnail(
    field_id: str,
    cache: CacheDep,
    _user: dict = Depends(get_current_user),
) -> TileInfoResponse:
    thumbnail_url = await cache.get_thumbnail(field_id)
    if not thumbnail_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No thumbnail available for field '{field_id}'. Run an analysis first.",
        )
    return TileInfoResponse(fieldId=field_id, thumbnailUrl=thumbnail_url)  # noqa: N815


@router.get(
    "/{field_id}/alerts",
    response_model=AlertListResponse,
    summary="Get agronomic alerts for a field",
)
async def get_field_alerts(
    field_id: str,
    limit: int = 50,
    offset: int = 0,
    use_case: GetFieldAlertsUseCase = Depends(get_field_alerts_use_case),
    _user: dict = Depends(get_current_user),
) -> AlertListResponse:
    try:
        alerts = await use_case.execute(
            GetFieldAlertsQuery(field_id=field_id, limit=limit, offset=offset)
        )
        return AlertListResponse(
            fieldId=field_id,  # noqa: N815
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
