from datetime import datetime
from typing import Any

import structlog

from src.application.dto.analysis_dto import (
    AlertDTO,
    FieldAnalysisDTO,
    VegetationDTO,
    VisualizationDTO,
    WaterDTO,
)
from src.application.ports.cache_port import AbstractCacheService
from src.application.queries.get_analysis_query import GetAnalysisQuery
from src.domain.repositories.alert_repository import AbstractAlertRepository
from src.domain.repositories.analysis_repository import AbstractAnalysisRepository
from src.domain.repositories.field_repository import AbstractFieldRepository
from src.domain.repositories.metrics_repository import AbstractMetricsRepository
from src.domain.repositories.observation_repository import AbstractObservationRepository
from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend
from src.shared.exceptions import AnalysisNotFoundException


def _dict_to_field_analysis_dto(d: dict[str, Any]) -> FieldAnalysisDTO:
    veg = d.get("vegetation")
    water = d.get("water")
    viz = d.get("visualization")
    return FieldAnalysisDTO(
        field_id=d["field_id"],
        analysis_id=d["analysis_id"],
        analysis_date=datetime.fromisoformat(d["analysis_date"]),
        status=AnalysisStatus(d["status"]),
        vegetation=VegetationDTO(
            mean_ndvi=veg["mean_ndvi"],
            min_ndvi=veg["min_ndvi"],
            max_ndvi=veg["max_ndvi"],
            std_ndvi=veg["std_ndvi"],
            trend=VegetationTrend(veg["trend"]),
            health=VegetationHealth(veg["health"]),
        ) if veg else None,
        water=WaterDTO(mean_ndmi=water.get("mean_ndmi", water.get("mean_ndwi"))) if water else None,
        alerts=[
            AlertDTO(
                id=a["id"],
                severity=AlertSeverity(a["severity"]),
                alert_type=AlertType(a["alert_type"]),
                message=a["message"],
                created_at=datetime.fromisoformat(a["created_at"]),
            )
            for a in d.get("alerts", [])
        ],
        visualization=VisualizationDTO(
            tile_url=viz.get("tile_url"),
            thumbnail_url=viz.get("thumbnail_url"),
        ) if viz else None,
        cloud_coverage=d.get("cloud_coverage"),
    )

logger = structlog.get_logger(__name__)


class GetAnalysisUseCase:
    def __init__(
        self,
        analysis_repo: AbstractAnalysisRepository,
        field_repo: AbstractFieldRepository,
        metrics_repo: AbstractMetricsRepository,
        observation_repo: AbstractObservationRepository,
        alert_repo: AbstractAlertRepository,
        cache_service: AbstractCacheService,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._field_repo = field_repo
        self._metrics_repo = metrics_repo
        self._observation_repo = observation_repo
        self._alert_repo = alert_repo
        self._cache = cache_service

    async def execute(self, query: GetAnalysisQuery) -> FieldAnalysisDTO:
        cached = await self._cache.get_analysis(query.analysis_id)
        if cached is not None:
            return _dict_to_field_analysis_dto(cached)

        analysis = await self._analysis_repo.get_by_id(query.analysis_id)
        if analysis is None:
            raise AnalysisNotFoundException(query.analysis_id)

        field = await self._field_repo.get_by_id(analysis.field_id)
        external_field_id = field.external_id if field else analysis.field_id

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
            water_dto = WaterDTO(mean_ndmi=metrics.ndmi_mean)

        alerts = [
            AlertDTO(
                id=a.id,
                severity=a.severity,
                alert_type=a.alert_type,
                message=a.message,
                created_at=a.created_at,
            )
            for a in raw_alerts
        ]

        visualization = None
        tile_url = await self._cache.get_tiles(external_field_id)
        thumbnail_url = await self._cache.get_thumbnail(external_field_id)
        if tile_url or thumbnail_url:
            visualization = VisualizationDTO(tile_url=tile_url, thumbnail_url=thumbnail_url)

        dto = FieldAnalysisDTO(
            field_id=external_field_id,
            analysis_id=analysis.id,
            analysis_date=analysis.completed_at or analysis.created_at,
            status=analysis.status,
            vegetation=vegetation_dto,
            water=water_dto,
            alerts=alerts,
            visualization=visualization,
            cloud_coverage=observation.cloud_coverage if observation else None,
        )

        if analysis.is_terminal:
            await self._cache.set_analysis(query.analysis_id, dto)

        return dto
