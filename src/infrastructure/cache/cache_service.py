import json
from dataclasses import asdict
from typing import Any

import structlog

from src.application.ports.cache_port import AbstractCacheService
from src.shared.config import get_settings

logger = structlog.get_logger(__name__)


class RedisCacheService(AbstractCacheService):
    def __init__(self, redis: Any) -> None:
        self._redis = redis
        self._settings = get_settings()

    def _latest_key(self, field_id: str) -> str:
        return f"petalia:latest:{field_id}"

    def _timeseries_key(self, field_id: str) -> str:
        return f"petalia:timeseries:{field_id}"

    def _tiles_key(self, field_id: str) -> str:
        return f"petalia:tiles:{field_id}"

    def _thumbnail_key(self, field_id: str) -> str:
        return f"petalia:thumbnail:{field_id}"

    def _analysis_key(self, analysis_id: str) -> str:
        return f"petalia:analysis:{analysis_id}"

    def _serialize(self, data: Any) -> str:
        if hasattr(data, "__dataclass_fields__"):
            return json.dumps(asdict(data), default=str)
        return json.dumps(data, default=str)

    async def get_latest(self, field_id: str) -> dict | None:
        raw = await self._redis.get(self._latest_key(field_id))
        if raw:
            return json.loads(raw)
        return None

    async def set_latest(self, field_id: str, data: Any) -> None:
        await self._redis.setex(
            self._latest_key(field_id),
            self._settings.redis_cache_ttl_latest,
            self._serialize(data),
        )
        logger.debug("cache_set_latest", field_id=field_id)

    async def get_timeseries(self, field_id: str) -> dict | None:
        raw = await self._redis.get(self._timeseries_key(field_id))
        if raw:
            return json.loads(raw)
        return None

    async def set_timeseries(self, field_id: str, data: Any) -> None:
        await self._redis.setex(
            self._timeseries_key(field_id),
            self._settings.redis_cache_ttl_timeseries,
            self._serialize(data),
        )

    async def get_tiles(self, field_id: str) -> str | None:
        return await self._redis.get(self._tiles_key(field_id))

    async def set_tiles(self, field_id: str, tile_url: str) -> None:
        await self._redis.setex(
            self._tiles_key(field_id),
            self._settings.redis_cache_ttl_tiles,
            tile_url,
        )

    async def get_thumbnail(self, field_id: str) -> str | None:
        return await self._redis.get(self._thumbnail_key(field_id))

    async def set_thumbnail(self, field_id: str, thumbnail_url: str) -> None:
        await self._redis.setex(
            self._thumbnail_key(field_id),
            self._settings.redis_cache_ttl_tiles,
            thumbnail_url,
        )

    async def get_analysis(self, analysis_id: str) -> dict | None:
        raw = await self._redis.get(self._analysis_key(analysis_id))
        if raw:
            return json.loads(raw)
        return None

    async def set_analysis(self, analysis_id: str, data: Any) -> None:
        await self._redis.setex(
            self._analysis_key(analysis_id),
            self._settings.redis_cache_ttl_latest,
            self._serialize(data),
        )

    async def invalidate_field(self, field_id: str) -> None:
        # Only invalidate analysis-derived caches; tiles/thumbnails have their own 30-day TTL
        keys = [
            self._latest_key(field_id),
            self._timeseries_key(field_id),
        ]
        await self._redis.delete(*keys)
        logger.info("cache_invalidated", field_id=field_id)
