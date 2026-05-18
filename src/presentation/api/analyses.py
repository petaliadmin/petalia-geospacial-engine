from fastapi import APIRouter, Depends, HTTPException, status

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
    AlertResponse,
    AnalysisDetailResponse,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    VegetationResponse,
    VisualizationResponse,
    WaterResponse,
)
from src.shared.exceptions import (
    AnalysisAlreadyRunningException,
    AnalysisNotFoundException,
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
                field_id=payload.fieldId,  # noqa: N815
                geometry=payload.geometry,
                requested_metrics=payload.requestedMetrics,  # noqa: N815
            )
        )
        return CreateAnalysisResponse(
            analysisId=result.analysis_id,  # noqa: N815
            status=result.status,
            fieldId=result.field_id,  # noqa: N815
            createdAt=result.created_at,  # noqa: N815
        )
    except InvalidGeometryException as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message)
    except AnalysisAlreadyRunningException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)


@router.get(
    "/{analysis_id}",
    response_model=AnalysisDetailResponse,
    summary="Get analysis results by ID",
)
async def get_analysis(
    analysis_id: str,
    use_case: GetAnalysisUseCase = Depends(get_get_analysis_use_case),
    _user: dict = Depends(get_current_user),
) -> AnalysisDetailResponse:
    try:
        dto = await use_case.execute(GetAnalysisQuery(analysis_id=analysis_id))
        return _dto_to_detail_response(dto)
    except AnalysisNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


def _dto_to_detail_response(dto: FieldAnalysisDTO) -> AnalysisDetailResponse:
    return AnalysisDetailResponse(
        fieldId=dto.field_id,  # noqa: N815
        analysisId=dto.analysis_id,  # noqa: N815
        analysisDate=dto.analysis_date,  # noqa: N815
        status=dto.status,
        vegetation=VegetationResponse(
            meanNdvi=dto.vegetation.mean_ndvi,  # noqa: N815
            minNdvi=dto.vegetation.min_ndvi,  # noqa: N815
            maxNdvi=dto.vegetation.max_ndvi,  # noqa: N815
            stdNdvi=dto.vegetation.std_ndvi,  # noqa: N815
            trend=dto.vegetation.trend,
            health=dto.vegetation.health,
        ) if dto.vegetation else None,
        water=WaterResponse(meanNdwi=dto.water.mean_ndwi) if dto.water else None,  # noqa: N815
        alerts=[
            AlertResponse(
                id=a.id,
                severity=a.severity,
                alertType=a.alert_type,  # noqa: N815
                message=a.message,
                createdAt=a.created_at,  # noqa: N815
            )
            for a in dto.alerts
        ],
        visualization=VisualizationResponse(
            tileUrl=dto.visualization.tile_url,  # noqa: N815
            thumbnailUrl=dto.visualization.thumbnail_url,  # noqa: N815
        ) if dto.visualization else None,
        cloudCoverage=dto.cloud_coverage,  # noqa: N815
    )
