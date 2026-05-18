"""API endpoint tests — fields router: S1-3 TTL tiles, S4-3 timeseries multi-index.

Tests mock at the use-case layer using patch() — no database or GEE needed.
"""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6], [-1.5, 47.6], [-1.5, 47.5]]],
}


# ---------------------------------------------------------------------------
# S2-3: Tiles TTL must be ≤ 172800 (48h)
# ---------------------------------------------------------------------------

def test_tiles_ttl_setting_is_at_most_48h() -> None:
    """S2-3: REDIS_CACHE_TTL_TILES must be ≤ 172800 (48h).

    GEE tile URLs expire within 1-7 days. Caching beyond 48h serves dead URLs.
    """
    from src.shared.config import get_settings
    settings = get_settings()
    assert settings.redis_cache_ttl_tiles <= 172800, (
        f"redis_cache_ttl_tiles={settings.redis_cache_ttl_tiles} > 172800 (48h). "
        "GEE tile URLs expire — reduce TTL. (S2-3)"
    )


# ---------------------------------------------------------------------------
# S4-3: Timeseries endpoint returns multi-index fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeseries_response_contains_ndmi_not_ndwi(async_client, api_key_headers):
    """S1-3 + S4-3: timeseries entries must have ndmiMean, not ndwiMean."""
    from src.application.dto.analysis_dto import FieldTimeseriesDTO, TimeseriesEntryDTO

    dto = FieldTimeseriesDTO(
        field_id="field_001",
        total=2,
        entries=[
            TimeseriesEntryDTO(
                analysis_id=f"ana_{i}",
                analysis_date=datetime.now(UTC),
                ndvi_mean=0.70 + i * 0.02,
                ndmi_mean=0.08,  # S1-3
                ndre_mean=0.28,  # S4-3
                savi_mean=0.48,  # S4-3
                evi2_mean=0.61,  # S4-3
                cloud_coverage=0.10,
                trend=VegetationTrend.UP,
                health=VegetationHealth.GOOD,
            )
            for i in range(2)
        ],
    )

    with patch(
        "src.application.use_cases.get_field_timeseries_use_case.GetFieldTimeseriesUseCase.execute",
        new_callable=AsyncMock,
        return_value=dto,
    ):
        response = await async_client.get(
            "/v1/fields/field_001/timeseries",
            headers=api_key_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["entries"]) == 2

    entry = data["entries"][0]
    # S1-3
    assert "ndmiMean" in entry, "S1-3: ndmiMean must be present in timeseries entry"
    assert "ndwiMean" not in entry, "S1-3: ndwiMean must NOT appear"
    # S4-3
    assert "ndreMean" in entry, "S4-3: ndreMean must be present in timeseries entry"
    assert "saviMean" in entry, "S4-3: saviMean must be present"
    assert "evi2Mean" in entry, "S4-3: evi2Mean must be present"
    assert entry["ndreMean"] == 0.28
    assert entry["saviMean"] == 0.48
    assert entry["evi2Mean"] == 0.61


@pytest.mark.asyncio
async def test_timeseries_backward_compat_null_new_indices(async_client, api_key_headers):
    """S4-3 backward compat: entries without NDRE/SAVI/EVI2 must return null."""
    from src.application.dto.analysis_dto import FieldTimeseriesDTO, TimeseriesEntryDTO

    dto = FieldTimeseriesDTO(
        field_id="field_old",
        total=1,
        entries=[
            TimeseriesEntryDTO(
                analysis_id="ana_old",
                analysis_date=datetime.now(UTC),
                ndvi_mean=0.65,
                ndmi_mean=0.05,
                ndre_mean=None,  # Pre-S2-1 analysis
                savi_mean=None,
                evi2_mean=None,
                cloud_coverage=0.20,
                trend=VegetationTrend.STABLE,
                health=VegetationHealth.GOOD,
            )
        ],
    )

    with patch(
        "src.application.use_cases.get_field_timeseries_use_case.GetFieldTimeseriesUseCase.execute",
        new_callable=AsyncMock,
        return_value=dto,
    ):
        response = await async_client.get(
            "/v1/fields/field_old/timeseries",
            headers=api_key_headers,
        )

    assert response.status_code == 200
    entry = response.json()["entries"][0]
    assert entry["ndreMean"] is None, "Pre-S2-1 analysis: ndreMean must be null"
    assert entry["saviMean"] is None
    assert entry["evi2Mean"] is None


@pytest.mark.asyncio
async def test_get_field_latest_not_found(async_client, api_key_headers):
    """GET /v1/fields/{id}/latest returns 404 for unknown field."""
    from src.shared.exceptions import FieldNotFoundException

    with patch(
        "src.application.use_cases.get_field_latest_use_case.GetFieldLatestUseCase.execute",
        new_callable=AsyncMock,
        side_effect=FieldNotFoundException("unknown-field"),
    ):
        response = await async_client.get(
            "/v1/fields/unknown-field/latest",
            headers=api_key_headers,
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_field_alerts_requires_auth(async_client):
    """GET /v1/fields/{id}/alerts must return 401 without authentication."""
    response = await async_client.get("/v1/fields/field_001/alerts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_field_tiles_not_found(async_client, api_key_headers):
    """GET /v1/fields/{id}/tiles returns 404 when no tiles cached."""
    response = await async_client.get(
        "/v1/fields/field_with_no_tiles/tiles",
        headers=api_key_headers,
    )
    # mock_cache.get_tiles returns None by default (from conftest mock_cache fixture)
    assert response.status_code == 404
