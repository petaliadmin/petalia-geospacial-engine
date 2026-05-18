import structlog

from src.application.dto.analysis_dto import (
    AlertDTO,
    FieldAnalysisDTO,
    VisualizationDTO,
    VegetationDTO,
    WaterDTO,
)
from src.application.queries.get_field_latest_query import GetFieldLatestQuery
from src.domain.repositories.alert_repository import AbstractAlertRepository
from src.domain.repositories.analysis_repository import AbstractAnalysisRepository
from src.domain.repositories.field_repository import AbstractFieldRepository
from src.domain.repositories.metrics_repository import AbstractMetricsRepository
from src.domain.repositories.observation_repository import AbstractObservationRepository
from src.application.ports.cache_port import AbstractCacheService
from src.shared.config import get_settings
from src.shared.exceptions import FieldNotFoundException
from src.shared.utils import is_within_hours

logger = structlog.get_logger(__name__)


class GetFieldLatestUseCase:
    def __init__(
        self,
        field_repo: AbstractFieldRepository,
        analysis_repo: AbstractAnalysisRepository,
        metrics_repo: AbstractMetricsRepository,
        observation_repo: AbstractObservationRepository,
        alert_repo: AbstractAlertRepository,
        cache_service: AbstractCacheService,
    ) -> None:
        self._field_repo = field_repo
        self._analysis_repo = analysis_repo
        self._metrics_repo = metrics_repo
        self._observation_repo = observation_repo
        self._alert_repo = alert_repo
        self._cache = cache_service
        self._settings = get_settings()

    async def execute(self, query: GetFieldLatestQuery) -> FieldAnalysisDTO:
        cached = await self._cache.get_latest(query.field_id)
        if cached is not None:
            logger.info("cache_hit_latest", field_id=query.field_id)
            return cached

        field = await self._field_repo.get_by_external_id(query.field_id)
        if field is None:
            raise FieldNotFoundException(query.field_id)

        analysis = await self._analysis_repo.get_latest_for_field(field.id)
        if analysis is None:
            raise FieldNotFoundException(query.field_id)

        metrics = await self._metrics_repo.get_by_analysis_id(analysis.id)
        observation = await self._observation_repo.get_by_analysis_id(analysis.id)
        raw_alerts = await self._alert_repo.get_by_analysis_id(analysis.id)

        vegetation_dto = None
        water_dto = None
        if metrics:
            vegetation_dto = VegetationDTO(
                mean_ndvi=metrics.ndvi_mean,
                min_ndvi=metrics.ndvi_min,
                max_ndvi=metrics.ndvi_max,
                std_ndvi=metrics.ndvi_std,
                trend=metrics.trend,
                health=metrics.health,
            )
            water_dto = WaterDTO(mean_ndwi=metrics.ndwi_mean)

        tile_url = await self._cache.get_tiles(query.field_id)
        thumbnail_url = await self._cache.get_thumbnail(query.field_id)
        visualization = None
        if tile_url or thumbnail_url:
            visualization = VisualizationDTO(tile_url=tile_url, thumbnail_url=thumbnail_url)

        dto = FieldAnalysisDTO(
            field_id=query.field_id,
            analysis_id=analysis.id,
            analysis_date=analysis.completed_at or analysis.created_at,
            status=analysis.status,
            vegetation=vegetation_dto,
            water=water_dto,
            alerts=[
                AlertDTO(
                    id=a.id,
                    severity=a.severity,
                    alert_type=a.alert_type,
                    message=a.message,
                    created_at=a.created_at,
                )
                for a in raw_alerts
            ],
            visualization=visualization,
            cloud_coverage=observation.cloud_coverage if observation else None,
        )

        if analysis.is_terminal:
            await self._cache.set_latest(query.field_id, dto)

        return dto
