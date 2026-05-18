from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.cache.redis_client import get_redis
from src.infrastructure.database.connection import get_db_session
from src.shared.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict:
    return {"status": "ok", "service": get_settings().app_name}


@router.get("/health/ready", summary="Readiness probe — checks DB and Redis")
async def health_ready() -> dict:
    results: dict[str, str] = {}
    overall = "ok"

    try:
        async for session in get_db_session():
            await session.execute(text("SELECT 1"))
        results["database"] = "ok"
    except Exception as exc:
        results["database"] = f"error: {exc}"
        overall = "degraded"

    try:
        redis = await get_redis()
        await redis.ping()
        results["redis"] = "ok"
    except Exception as exc:
        results["redis"] = f"error: {exc}"
        overall = "degraded"

    return {"status": overall, "checks": results}
