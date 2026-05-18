from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.use_cases import (
    CreateAnalysisUseCase,
    GetAnalysisUseCase,
    GetFieldAlertsUseCase,
    GetFieldLatestUseCase,
    GetFieldTimeseriesUseCase,
)
from src.domain.services.alert_detection_service import AlertDetectionService
from src.domain.services.analysis_domain_service import AnalysisDomainService
from src.infrastructure.cache.cache_service import RedisCacheService
from src.infrastructure.cache.redis_client import get_redis
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.repositories import (
    SQLAlertRepository,
    SQLAnalysisRepository,
    SQLFieldRepository,
    SQLMetricsRepository,
    SQLObservationRepository,
)
from src.infrastructure.messaging.event_publisher import CeleryTaskPublisher


async def get_session_dep() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session_dep)]


async def get_cache_service(redis=Depends(get_redis)) -> RedisCacheService:
    return RedisCacheService(redis)


CacheDep = Annotated[RedisCacheService, Depends(get_cache_service)]


def get_field_repo(session: SessionDep) -> SQLFieldRepository:
    return SQLFieldRepository(session)


def get_analysis_repo(session: SessionDep) -> SQLAnalysisRepository:
    return SQLAnalysisRepository(session)


def get_observation_repo(session: SessionDep) -> SQLObservationRepository:
    return SQLObservationRepository(session)


def get_metrics_repo(session: SessionDep) -> SQLMetricsRepository:
    return SQLMetricsRepository(session)


def get_alert_repo(session: SessionDep) -> SQLAlertRepository:
    return SQLAlertRepository(session)


def get_create_analysis_use_case(
    session: SessionDep,
    cache: CacheDep,
) -> CreateAnalysisUseCase:
    return CreateAnalysisUseCase(
        field_repo=SQLFieldRepository(session),
        analysis_repo=SQLAnalysisRepository(session),
        domain_service=AnalysisDomainService(),
        task_publisher=CeleryTaskPublisher(),
    )


def get_get_analysis_use_case(
    session: SessionDep,
    cache: CacheDep,
) -> GetAnalysisUseCase:
    return GetAnalysisUseCase(
        analysis_repo=SQLAnalysisRepository(session),
        field_repo=SQLFieldRepository(session),
        metrics_repo=SQLMetricsRepository(session),
        observation_repo=SQLObservationRepository(session),
        alert_repo=SQLAlertRepository(session),
        cache_service=cache,
    )


def get_field_latest_use_case(
    session: SessionDep,
    cache: CacheDep,
) -> GetFieldLatestUseCase:
    return GetFieldLatestUseCase(
        field_repo=SQLFieldRepository(session),
        analysis_repo=SQLAnalysisRepository(session),
        metrics_repo=SQLMetricsRepository(session),
        observation_repo=SQLObservationRepository(session),
        alert_repo=SQLAlertRepository(session),
        cache_service=cache,
    )


def get_field_timeseries_use_case(
    session: SessionDep,
    cache: CacheDep,
) -> GetFieldTimeseriesUseCase:
    return GetFieldTimeseriesUseCase(
        field_repo=SQLFieldRepository(session),
        analysis_repo=SQLAnalysisRepository(session),
        metrics_repo=SQLMetricsRepository(session),
        observation_repo=SQLObservationRepository(session),
        cache_service=cache,
    )


def get_field_alerts_use_case(
    session: SessionDep,
) -> GetFieldAlertsUseCase:
    return GetFieldAlertsUseCase(
        field_repo=SQLFieldRepository(session),
        alert_repo=SQLAlertRepository(session),
    )
