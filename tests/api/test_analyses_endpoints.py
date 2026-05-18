"""API endpoint tests — S1-3 ndmiMean in responses, S4-1 batch endpoint.

Tests mock at the use-case layer using patch() — no database or GEE needed.
"""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6], [-1.5, 47.6], [-1.5, 47.5]]],
}

CREATE_PAYLOAD = {
    "fieldId": "field_001",
    "geometry": GEOMETRY,
    "requestedMetrics": ["NDVI", "NDWI", "CLOUD", "TILES", "ALERTS"],
}


def _make_analysis_status_dto(field_id: str = "field_001", analysis_id: str = "ana_test123"):
    from src.application.dto.analysis_dto import AnalysisStatusDTO
    return AnalysisStatusDTO(
        analysis_id=analysis_id,
        status=AnalysisStatus.PENDING,
        field_id=field_id,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# S1-3: Verify response uses ndmiMean not ndwiMean
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_analysis_returns_202(async_client, api_key_headers):
    """POST /v1/analyses must return 202 ACCEPTED."""
    with patch(
        "src.application.use_cases.create_analysis_use_case.CreateAnalysisUseCase.execute",
        new_callable=AsyncMock,
        return_value=_make_analysis_status_dto(),
    ):
        response = await async_client.post(
            "/v1/analyses", json=CREATE_PAYLOAD, headers=api_key_headers
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert "analysisId" in data
    assert "fieldId" in data


@pytest.mark.asyncio
async def test_get_analysis_response_uses_ndmi_not_ndwi(async_client, api_key_headers):
    """S1-3: GET /v1/analyses/{id} response must contain 'meanNdmi', not 'meanNdwi'."""
    from src.application.dto.analysis_dto import (
        AlertDTO,
        FieldAnalysisDTO,
        VegetationDTO,
        VisualizationDTO,
        WaterDTO,
    )

    dto = FieldAnalysisDTO(
        field_id="field_001",
        analysis_id="ana_001",
        analysis_date=datetime.now(UTC),
        status=AnalysisStatus.COMPLETED,
        vegetation=VegetationDTO(
            mean_ndvi=0.72, min_ndvi=0.31, max_ndvi=0.91, std_ndvi=0.12,
            trend=VegetationTrend.UP, health=VegetationHealth.GOOD,
        ),
        water=WaterDTO(mean_ndmi=0.08),  # S1-3
        alerts=[],
        visualization=VisualizationDTO(tile_url=None, thumbnail_url=None),
        cloud_coverage=0.12,
    )

    with patch(
        "src.application.use_cases.get_analysis_use_case.GetAnalysisUseCase.execute",
        new_callable=AsyncMock,
        return_value=dto,
    ):
        response = await async_client.get("/v1/analyses/ana_001", headers=api_key_headers)

    assert response.status_code == 200
    data = response.json()

    # S1-3: Key assertion — API must use ndmiMean
    assert "water" in data
    assert "meanNdmi" in data["water"], (
        "S1-3: API response must contain 'meanNdmi', not 'meanNdwi'"
    )
    assert "meanNdwi" not in data.get("water", {}), (
        "S1-3: 'meanNdwi' must NOT appear in the response"
    )
    assert data["water"]["meanNdmi"] == 0.08


@pytest.mark.asyncio
async def test_create_analysis_requires_auth(async_client):
    """Unauthenticated requests must return 401."""
    response = await async_client.post("/v1/analyses", json=CREATE_PAYLOAD)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_analysis_area_too_large_returns_422(async_client, api_key_headers):
    """S3-4: Fields exceeding max area must return 422."""
    from src.shared.exceptions import InvalidGeometryException

    with patch(
        "src.application.use_cases.create_analysis_use_case.CreateAnalysisUseCase.execute",
        new_callable=AsyncMock,
        side_effect=InvalidGeometryException("Field area (60000 ha) exceeds maximum"),
    ):
        response = await async_client.post(
            "/v1/analyses", json=CREATE_PAYLOAD, headers=api_key_headers
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_analysis_not_found(async_client, api_key_headers):
    """GET /v1/analyses/{id} with unknown ID must return 404."""
    from src.shared.exceptions import AnalysisNotFoundException

    with patch(
        "src.application.use_cases.get_analysis_use_case.GetAnalysisUseCase.execute",
        new_callable=AsyncMock,
        side_effect=AnalysisNotFoundException("nonexistent-id"),
    ):
        response = await async_client.get(
            "/v1/analyses/nonexistent-id", headers=api_key_headers
        )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# S4-1: Batch endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_analysis_returns_202(async_client, api_key_headers):
    """S4-1: POST /v1/analyses/batch must return 202 with batch summary."""
    with patch(
        "src.application.use_cases.create_analysis_use_case.CreateAnalysisUseCase.execute",
        new_callable=AsyncMock,
    ) as mock_exec, patch(
        "src.infrastructure.workers.batch_analysis_worker.publish_batch_group"
    ) as mock_publish:
        mock_exec.side_effect = [
            _make_analysis_status_dto("field_A", "ana_001"),
            _make_analysis_status_dto("field_B", "ana_002"),
        ]
        mock_publish.return_value = "batch-uuid-1234"

        response = await async_client.post(
            "/v1/analyses/batch",
            json={
                "fields": [
                    {**CREATE_PAYLOAD, "fieldId": "field_A"},
                    {**CREATE_PAYLOAD, "fieldId": "field_B"},
                ]
            },
            headers=api_key_headers,
        )

    assert response.status_code == 202
    data = response.json()
    assert data["submitted"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_batch_analysis_partial_failure(async_client, api_key_headers):
    """S4-1: Partial failure must not abort the batch — failed items reported separately."""
    from src.shared.exceptions import InvalidGeometryException

    with patch(
        "src.application.use_cases.create_analysis_use_case.CreateAnalysisUseCase.execute",
        new_callable=AsyncMock,
    ) as mock_exec, patch(
        "src.infrastructure.workers.batch_analysis_worker.publish_batch_group"
    ):
        mock_exec.side_effect = [
            _make_analysis_status_dto("field_A", "ana_001"),  # succeeds
            InvalidGeometryException("invalid geometry on field_B"),  # fails
        ]

        response = await async_client.post(
            "/v1/analyses/batch",
            json={
                "fields": [
                    {**CREATE_PAYLOAD, "fieldId": "field_A"},
                    {**CREATE_PAYLOAD, "fieldId": "field_B"},
                ]
            },
            headers=api_key_headers,
        )

    assert response.status_code == 202
    data = response.json()
    assert data["succeeded"] == 1
    assert data["failed"] == 1
    failed_item = next(i for i in data["items"] if i["fieldId"] == "field_B")
    assert failed_item["status"] == "FAILED"
    assert failed_item["error"] is not None


@pytest.mark.asyncio
async def test_batch_status_running(async_client, api_key_headers):
    """S4-1: GET /batch/{batch_id}/status returns 'RUNNING' when chord not yet done."""
    with patch(
        "src.infrastructure.workers.batch_analysis_worker.get_batch_result",
        return_value=None,
    ):
        response = await async_client.get(
            "/v1/analyses/batch/non-existent-batch/status",
            headers=api_key_headers,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"


@pytest.mark.asyncio
async def test_batch_status_completed(async_client, api_key_headers):
    """S4-1: GET /batch/{batch_id}/status returns full result once chord completes."""
    mock_result = {
        "batch_id": "my-batch",
        "submitted": 2,
        "succeeded": 2,
        "failed": 0,
        "results": [],
    }
    with patch(
        "src.infrastructure.workers.batch_analysis_worker.get_batch_result",
        return_value=mock_result,
    ):
        response = await async_client.get(
            "/v1/analyses/batch/my-batch/status",
            headers=api_key_headers,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["succeeded"] == 2


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    """Health check must return 200."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
