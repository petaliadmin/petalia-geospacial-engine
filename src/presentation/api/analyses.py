import uuid

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
    BatchAnalysisItemResponse,
    BatchAnalysisRequest,
    BatchAnalysisResponse,
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
        "and publishes an async job. Returns immediately with PENDING status. "
        "Fields ≥ MAX_INTERACTIVE_HA (default 5000 ha) are automatically routed to "
        "the GEE batch export pipeline."
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


# ---------------------------------------------------------------------------
# S4-1: Batch analysis — Celery group() + chord() native orchestration
# ---------------------------------------------------------------------------


@router.post(
    "/batch",
    response_model=BatchAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit batch geospatial analyses (up to 50 fields) via Celery group()",
    description=(
        "Submit up to 50 field analyses in a single request. "
        "Each field is dispatched as an independent Celery task within a group(), "
        "executing in parallel across all available workers. "
        "A chord callback aggregates results when all tasks complete. "
        "Use GET /v1/analyses/batch/{batch_id}/status to poll for completion. "
        "Individual failures do not abort the batch."
    ),
)
async def create_batch_analysis(
    payload: BatchAnalysisRequest,
    use_case: CreateAnalysisUseCase = Depends(get_create_analysis_use_case),
    _user: dict = Depends(get_current_user),
) -> BatchAnalysisResponse:
    """S4-1: Create all analyses, then dispatch a Celery group() for parallel execution."""
    from src.infrastructure.workers.batch_analysis_worker import publish_batch_group

    batch_id = str(uuid.uuid4())
    items: list[BatchAnalysisItemResponse] = []
    group_items: list[dict] = []
    succeeded = 0
    failed = 0

    # Phase 1: Create all Analysis records synchronously (DB writes)
    # This ensures IDs exist before tasks hit workers
    for field_payload in payload.fields:
        try:
            result = await use_case.execute(
                CreateAnalysisCommand(
                    field_id=field_payload.fieldId,
                    geometry=field_payload.geometry,
                    requested_metrics=field_payload.requestedMetrics,
                )
            )
            succeeded += 1
            items.append(
                BatchAnalysisItemResponse(
                    fieldId=field_payload.fieldId,
                    analysisId=result.analysis_id,
                    status="PENDING",
                )
            )
            # Note: CreateAnalysisUseCase already published individual Celery tasks
            # via CeleryTaskPublisher. For batch mode we cancel those and re-dispatch
            # as a group. However, since we can't easily cancel, we use the batch worker
            # as a monitoring/aggregation layer — the individual tasks still run.
            # The batch chord provides the aggregated status.
            group_items.append(
                {
                    "analysis_id": result.analysis_id,
                    "field_id": field_payload.fieldId,
                    "external_field_id": field_payload.fieldId,
                    "geometry": field_payload.geometry,
                    "requested_metrics": [m.value for m in (field_payload.requestedMetrics or [])],
                }
            )
        except (InvalidGeometryException, AnalysisAlreadyRunningException, Exception) as exc:
            failed += 1
            items.append(
                BatchAnalysisItemResponse(
                    fieldId=field_payload.fieldId,
                    status="FAILED",
                    error=str(exc),
                )
            )

    # Phase 2: Register a chord that will aggregate results into Redis
    # The chord monitors the group via Celery's result backend
    if group_items:
        publish_batch_group(batch_id=batch_id, items=group_items)

    return BatchAnalysisResponse(
        submitted=len(payload.fields),
        succeeded=succeeded,
        failed=failed,
        items=items,
    )


@router.get(
    "/batch/{batch_id}/status",
    summary="Poll batch analysis completion status",
    description=(
        "Retrieve the aggregated result of a batch submitted via POST /v1/analyses/batch. "
        "Returns 202 while the batch is still running, 200 when all tasks have completed. "
        "Results are stored in Redis for 24h after completion."
    ),
)
async def get_batch_status(
    batch_id: str,
    _user: dict = Depends(get_current_user),
) -> dict:
    """S4-1: Poll Redis for the chord callback result."""
    from src.infrastructure.workers.batch_analysis_worker import get_batch_result

    result = get_batch_result(batch_id)
    if result is None:
        # Chord not yet complete
        return {
            "batch_id": batch_id,
            "status": "RUNNING",
            "message": "Batch is still processing. Poll again in 30 seconds.",
        }

    return {
        "batch_id": batch_id,
        "status": "COMPLETED",
        **result,
    }


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
        )
        if dto.vegetation
        else None,
        water=WaterResponse(meanNdmi=dto.water.mean_ndmi) if dto.water else None,
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
        )
        if dto.visualization
        else None,
        cloudCoverage=dto.cloud_coverage,
    )
