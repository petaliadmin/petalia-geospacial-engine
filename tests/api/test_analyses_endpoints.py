import pytest
from unittest.mock import AsyncMock, patch

from src.domain.value_objects.analysis_status import AnalysisStatus

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [[-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6], [-1.5, 47.6], [-1.5, 47.5]]
    ],
}

CREATE_PAYLOAD = {
    "fieldId": "field_001",
    "geometry": GEOMETRY,
    "requestedMetrics": ["NDVI", "NDWI", "CLOUD", "TILES", "ALERTS"],
}


@pytest.mark.asyncio
async def test_create_analysis_returns_202(async_client, api_key_headers):
    with patch(
        "src.application.use_cases.create_analysis_use_case.CreateAnalysisUseCase.execute",
        new_callable=AsyncMock,
    ) as mock_exec:
        from src.application.dto.analysis_dto import AnalysisStatusDTO
        from datetime import datetime, timezone

        mock_exec.return_value = AnalysisStatusDTO(
            analysis_id="ana_test123",
            status=AnalysisStatus.PENDING,
            field_id="field_001",
            created_at=datetime.now(timezone.utc),
        )

        response = await async_client.post(
            "/v1/analyses", json=CREATE_PAYLOAD, headers=api_key_headers
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert "analysisId" in data


@pytest.mark.asyncio
async def test_create_analysis_requires_auth(async_client):
    response = await async_client.post("/v1/analyses", json=CREATE_PAYLOAD)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_analysis_invalid_geometry(async_client, api_key_headers):
    payload = {**CREATE_PAYLOAD, "geometry": {"type": "INVALID"}}
    with patch(
        "src.application.use_cases.create_analysis_use_case.CreateAnalysisUseCase.execute",
        new_callable=AsyncMock,
        side_effect=__import__(
            "src.shared.exceptions", fromlist=["InvalidGeometryException"]
        ).InvalidGeometryException("bad geometry"),
    ):
        response = await async_client.post(
            "/v1/analyses", json=payload, headers=api_key_headers
        )
    assert response.status_code in (422, 400)


@pytest.mark.asyncio
async def test_get_analysis_not_found(async_client, api_key_headers):
    with patch(
        "src.application.use_cases.get_analysis_use_case.GetAnalysisUseCase.execute",
        new_callable=AsyncMock,
        side_effect=__import__(
            "src.shared.exceptions", fromlist=["AnalysisNotFoundException"]
        ).AnalysisNotFoundException("nonexistent-id"),
    ):
        response = await async_client.get(
            "/v1/analyses/nonexistent-id", headers=api_key_headers
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
