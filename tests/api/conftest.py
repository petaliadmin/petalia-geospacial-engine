"""API conftest — FastAPI async client with fully mocked DB and cache.

All API tests mock at the use-case layer, so no live database is needed here.
The session dependency is overridden with an AsyncMock to avoid any DB connection.
"""
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.presentation.api.dependencies import get_cache_service, get_session_dep


@pytest_asyncio.fixture
async def async_client(mock_cache) -> AsyncGenerator[AsyncClient, None]:
    mock_session = AsyncMock()

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_session_dep] = override_session
    app.dependency_overrides[get_cache_service] = lambda: mock_cache

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
