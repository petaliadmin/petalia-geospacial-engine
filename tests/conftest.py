"""Root conftest — pure fixtures only, no infrastructure imports.
DB/app fixtures live in tests/integration/conftest.py and tests/api/conftest.py.
"""
from src.domain.entities.vegetation_metrics import VegetationMetrics
from src.domain.value_objects.vegetation_trend import VegetationTrend


def make_metrics(
    ndvi_mean: float = 0.60,
    ndvi_min: float = 0.30,
    ndvi_max: float = 0.85,
    ndvi_std: float = 0.10,
    ndmi_mean: float = 0.05,
    ndre_mean: float | None = 0.30,
    savi_mean: float | None = 0.40,
    evi2_mean: float | None = 0.50,
    variability_index: float = 0.15,
    trend: VegetationTrend = VegetationTrend.STABLE,
    analysis_id: str = "test-analysis-id",
) -> VegetationMetrics:
    """Factory helper for VegetationMetrics — avoids DB dependency in unit tests."""
    return VegetationMetrics(
        id="test-metrics-id",
        analysis_id=analysis_id,
        ndvi_mean=ndvi_mean,
        ndvi_min=ndvi_min,
        ndvi_max=ndvi_max,
        ndvi_std=ndvi_std,
        ndmi_mean=ndmi_mean,
        ndre_mean=ndre_mean,
        savi_mean=savi_mean,
        evi2_mean=evi2_mean,
        variability_index=variability_index,
        trend=trend,
    )
import asyncio
from unittest.mock import AsyncMock

import pytest

from src.presentation.middlewares.auth_middleware import create_access_token
from src.shared.config import get_settings

SAMPLE_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [
            [-1.5, 47.5],
            [-1.4, 47.5],
            [-1.4, 47.6],
            [-1.5, 47.6],
            [-1.5, 47.5],
        ]
    ],
}


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get_latest.return_value = None
    cache.get_timeseries.return_value = None
    cache.get_tiles.return_value = None
    cache.get_thumbnail.return_value = None
    cache.get_analysis.return_value = None
    cache.set_latest = AsyncMock()
    cache.set_timeseries = AsyncMock()
    cache.set_tiles = AsyncMock()
    cache.set_thumbnail = AsyncMock()
    cache.set_analysis = AsyncMock()
    cache.invalidate_field = AsyncMock()
    return cache


@pytest.fixture
def auth_headers() -> dict:
    token = create_access_token({"sub": "test-user"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_key_headers() -> dict:
    settings = get_settings()
    return {settings.api_key_header: settings.api_key_value}
