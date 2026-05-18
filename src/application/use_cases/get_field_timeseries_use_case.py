import structlog

from src.application.dto.analysis_dto import FieldTimeseriesDTO, TimeseriesEntryDTO
from src.application.ports.cache_port import AbstractCacheService
from src.application.queries.get_field_timeseries_query import GetFieldTimeseriesQuery
from src.domain.repositories.analysis_repository import AbstractAnalysisRepository
from src.domain.repositories.field_repository import AbstractFieldRepository
from src.domain.repositories.metrics_repository import AbstractMetricsRepository
from src.domain.repositories.observation_repository import AbstractObservationRepository
from src.shared.exceptions import FieldNotFoundException

logger = structlog.get_logger(__name__)


class GetFieldTimeseriesUseCase:
    def __init__(
        self,
        field_repo: AbstractFieldRepository,
        analysis_repo: AbstractAnalysisRepository,
        metrics_repo: AbstractMetricsRepository,
        observation_repo: AbstractObservationRepository,
        cache_service: AbstractCacheService,
    ) -> None:
        self._field_repo = field_repo
        self._analysis_repo = analysis_repo
        self._metrics_repo = metrics_repo
        self._observation_repo = observation_repo
        self._cache = cache_service

    async def execute(self, query: GetFieldTimeseriesQuery) -> FieldTimeseriesDTO:
        cached = await self._cache.get_timeseries(query.field_id)
        if cached is not None:
            logger.info("cache_hit_timeseries", field_id=query.field_id)
            return cached

        field = await self._field_repo.get_by_external_id(query.field_id)
        if field is None:
            raise FieldNotFoundException(query.field_id)

        all_metrics = await self._metrics_repo.get_timeseries_for_field(
            field.id, limit=query.limit
        )
        analyses = await self._analysis_repo.list_for_field(field.id, limit=query.limit)
        analysis_map = {a.id: a for a in analyses}

        entries: list[TimeseriesEntryDTO] = []
        for m in all_metrics:
            analysis = analysis_map.get(m.analysis_id)
            if not analysis:
                continue
            obs = await self._observation_repo.get_by_analysis_id(m.analysis_id)
            entries.append(
                TimeseriesEntryDTO(
                    analysis_id=m.analysis_id,
                    analysis_date=analysis.completed_at or analysis.created_at,
                    ndvi_mean=m.ndvi_mean,
                    # S1-3: was ndwi_mean — renamed to ndmi_mean throughout
                    ndmi_mean=m.ndmi_mean,
                    # S4-3: Multi-index timeseries — None for pre-existing analyses
                    ndre_mean=getattr(m, "ndre_mean", None),
                    savi_mean=getattr(m, "savi_mean", None),
                    evi2_mean=getattr(m, "evi2_mean", None),
                    cloud_coverage=obs.cloud_coverage if obs else None,
                    trend=m.trend,
                    health=m.health,
                )
            )

        dto = FieldTimeseriesDTO(
            field_id=query.field_id,
            entries=entries,
            total=len(entries),
        )

        await self._cache.set_timeseries(query.field_id, dto)
        return dto
