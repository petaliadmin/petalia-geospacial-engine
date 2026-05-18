"""Root conftest — pure fixtures only, no infrastructure imports.
DB/app fixtures live in tests/integration/conftest.py and tests/api/conftest.py.
"""
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


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
