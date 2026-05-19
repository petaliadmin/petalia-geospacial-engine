from typing import Any

import redis
import redis.asyncio as aioredis
from redis.asyncio import Redis

from src.shared.config import get_settings

_redis_client: Redis[Any] | None = None
_redis_sync_client: redis.Redis[Any] | None = None


async def get_redis() -> Redis[Any]:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


def get_redis_sync() -> redis.Redis[Any]:
    """Synchronous Redis client for use inside Celery tasks (non-async context).

    Celery tasks run in a sync context. Using the async client inside them
    requires an event loop which may not exist. This provides a simple
    synchronous connection for batch result storage.
    """
    global _redis_sync_client
    if _redis_sync_client is None:
        settings = get_settings()
        _redis_sync_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_sync_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
