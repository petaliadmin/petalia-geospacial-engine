from fastapi import APIRouter, Depends, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.application.commands.create_analysis_command import CreateAnalysisCommand
from src.application.dto.analysis_dto import FieldAnalysisDTO
from src.application.queries.get_analysis_query import GetAnalysisQuery
from src.application.use_cases import CreateAnalysisUseCase, GetAnalysisUseCase
from src.presentation.api.dependencies import (
    get_create_analysis_use_case,
    get_get_analysis_use_case,
)
from src.presentation.middlewares.auth_middleware import get_current_user
from src.presentation.schemas.analysis_schemas import (
    AnalysisDetailResponse,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    AlertResponse,
    VegetationResponse,
    WaterResponse,
    VisualizationResponse,
)
from src.shared.exceptions import (
    AnalysisNotFoundException,
    AnalysisAlreadyRunningException,
    InvalidGeometryException,
)

router = APIRouter(prefix="/v1/analyses", tags=["Analyses"])


@router.post(
    "",
    response_model=CreateAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new geospatial analysis",
    description=(
        "Accepts a field geometry and list of requested metrics, creates an Analysis, "
        "and publishes an async job. Returns immediately with PENDING status."
    ),
)
async def create_analysis(
    payload: CreateAnalysisRequest,
    use_case: CreateAnalysisUseCase = Depends(get_create_analysis_use_case),
    _user: dict = Depends(get_current_user),
) -> CreateAnalysisResponse:
    try:
        result = await use_case.execute(
            CreateAnalysisCommand(
                field_id=payload.fieldId,
                geometry=payload.geometry,
                requested_metrics=payload.requestedMetrics,
            )
        )
        return CreateAnalysisResponse(
            analysisId=result.analysis_id,
            status=result.status,
            fieldId=result.field_id,
            createdAt=result.created_at,
        )
    except InvalidGeometryException as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message)
    except AnalysisAlreadyRunningException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)


@router.get(
    "/{analysisId}",
    response_model=AnalysisDetailResponse,
    summary="Get analysis results by ID",
)
async def get_analysis(
    analysisId: str,
    use_case: GetAnalysisUseCase = Depends(get_get_analysis_use_case),
    _user: dict = Depends(get_current_user),
) -> AnalysisDetailResponse:
    try:
        dto = await use_case.execute(GetAnalysisQuery(analysis_id=analysisId))
        return _dto_to_detail_response(dto)
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


def _dto_to_detail_response(dto: FieldAnalysisDTO) -> AnalysisDetailResponse:
    return AnalysisDetailResponse(
        fieldId=dto.field_id,
        analysisId=dto.analysis_id,
        analysisDate=dto.analysis_date,
        status=dto.status,
        vegetation=VegetationResponse(
            meanNdvi=dto.vegetation.mean_ndvi,
            minNdvi=dto.vegetation.min_ndvi,
            maxNdvi=dto.vegetation.max_ndvi,
            stdNdvi=dto.vegetation.std_ndvi,
            trend=dto.vegetation.trend,
            health=dto.vegetation.health,
        ) if dto.vegetation else None,
        water=WaterResponse(meanNdwi=dto.water.mean_ndwi) if dto.water else None,
        alerts=[
            AlertResponse(
                id=a.id,
                severity=a.severity,
                alertType=a.alert_type,
                message=a.message,
                createdAt=a.created_at,
            )
            for a in dto.alerts
        ],
        visualization=VisualizationResponse(
            tileUrl=dto.visualization.tile_url,
            thumbnailUrl=dto.visualization.thumbnail_url,
        ) if dto.visualization else None,
        cloudCoverage=dto.cloud_coverage,
    )
