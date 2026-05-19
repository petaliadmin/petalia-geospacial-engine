from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Callable, cast

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from src.infrastructure.cache.redis_client import close_redis
from src.infrastructure.database.connection import close_engine
from src.infrastructure.monitoring.logging import configure_logging
from src.infrastructure.monitoring.tracing import configure_tracing
from src.presentation.api import api_router
from src.presentation.middlewares.logging_middleware import RequestLoggingMiddleware
from src.shared.config import get_settings
from src.shared.exceptions import DomainException


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()

    import structlog

    log = structlog.get_logger(__name__)
    log.info("service_starting", version=settings.app_version, env=settings.app_env)

    yield

    log.info("service_stopping")
    await close_redis()
    await close_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Petalia Geospatial Engine",
        description=(
            "**Spatial Intelligence as a Service**\n\n"
            "Geospatial analysis engine for Petalia Field Pro. "
            "Submit field geometries and receive satellite-derived vegetation metrics, "
            "water stress indices, interactive tile maps, and agronomic alerts."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        cast(Callable[[Request, Exception], JSONResponse], _rate_limit_exceeded_handler),
    )
    app.add_middleware(SlowAPIMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Prometheus metrics
    if settings.prometheus_enabled:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # Tracing
    configure_tracing(app)

    # Routes
    app.include_router(api_router)

    # Global exception handlers
    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        import structlog

        structlog.get_logger(__name__).error("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
        )

    return app


app = create_app()
