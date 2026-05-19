from typing import Any
import structlog

from src.application.commands.create_analysis_command import CreateAnalysisCommand
from src.application.dto.analysis_dto import AnalysisStatusDTO
from src.domain.entities.analysis import Analysis
from src.domain.entities.field import Field
from src.domain.repositories.analysis_repository import AbstractAnalysisRepository
from src.domain.repositories.field_repository import AbstractFieldRepository
from src.domain.services.analysis_domain_service import AnalysisDomainService
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.shared.config import get_settings
from src.shared.exceptions import InvalidGeometryException
from src.shared.utils import compute_area_hectares, validate_geojson_geometry

logger = structlog.get_logger(__name__)


class CreateAnalysisUseCase:
    def __init__(
        self,
        field_repo: AbstractFieldRepository,
        analysis_repo: AbstractAnalysisRepository,
        domain_service: AnalysisDomainService,
        task_publisher: "AbstractTaskPublisher",
    ) -> None:
        self._field_repo = field_repo
        self._analysis_repo = analysis_repo
        self._domain_service = domain_service
        self._task_publisher = task_publisher
        self._settings = get_settings()

    async def execute(self, command: CreateAnalysisCommand) -> AnalysisStatusDTO:
        log = logger.bind(field_id=command.field_id)

        try:
            validate_geojson_geometry(command.geometry)
        except ValueError as exc:
            raise InvalidGeometryException(str(exc)) from exc

        # S3-4: Validate field area before creating analysis.
        # Very large parcels (> max_field_area_ha) cannot be processed with interactive
        # GEE calls — they would hit the 120s timeout. Users must split the geometry
        # or wait for the batch export feature (S4-4).
        area_ha = compute_area_hectares(command.geometry)
        max_area = self._settings.max_field_area_ha
        if area_ha > max_area:
            raise InvalidGeometryException(
                f"Field area ({area_ha:.0f} ha) exceeds the maximum allowed for interactive "
                f"analysis ({max_area:,.0f} ha). Please split the geometry into smaller parcels."
            )

        field = await self._field_repo.get_by_external_id(command.field_id)
        if field is None:
            field = Field.create(
                external_id=command.field_id,
                geometry=command.geometry,
                area_ha=area_ha,
            )
            field = await self._field_repo.save(field)
            log.info("field_created", field_internal_id=field.id, area_ha=field.area_ha)
        else:
            field.update_geometry(command.geometry, area_ha)
            field = await self._field_repo.update(field)

        running = await self._analysis_repo.get_running_for_field(field.id)
        self._domain_service.validate_can_create_analysis(field, running)

        metrics = command.requested_metrics or [
            RequestedMetric.NDVI,
            RequestedMetric.NDWI,
            RequestedMetric.CLOUD,
            RequestedMetric.TILES,
            RequestedMetric.ALERTS,
        ]

        analysis = Analysis.create(
            field_id=field.id,
            requested_metrics=metrics,
        )
        analysis = await self._analysis_repo.save(analysis)
        log.info("analysis_created", analysis_id=analysis.id, area_ha=area_ha)

        await self._task_publisher.publish_analysis_job(
            analysis_id=analysis.id,
            field_id=field.id,
            external_field_id=command.field_id,
            geometry=command.geometry,
            requested_metrics=[m.value for m in metrics],
            area_ha=area_ha,
        )

        return AnalysisStatusDTO(
            analysis_id=analysis.id,
            status=analysis.status,
            field_id=command.field_id,
            created_at=analysis.created_at,
        )


class AbstractTaskPublisher:
    async def publish_analysis_job(
        self,
        analysis_id: str,
        field_id: str,
        external_field_id: str,
        geometry: dict[str, Any],
        requested_metrics: list[str],
        area_ha: float = 0.0,
    ) -> None:
        raise NotImplementedError
