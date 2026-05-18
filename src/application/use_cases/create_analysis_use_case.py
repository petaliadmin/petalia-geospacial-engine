import structlog

from src.application.commands.create_analysis_command import CreateAnalysisCommand
from src.application.dto.analysis_dto import AnalysisStatusDTO
from src.domain.entities.analysis import Analysis
from src.domain.entities.field import Field
from src.domain.repositories.analysis_repository import AbstractAnalysisRepository
from src.domain.repositories.field_repository import AbstractFieldRepository
from src.domain.services.analysis_domain_service import AnalysisDomainService
from src.domain.value_objects.requested_metrics import RequestedMetric
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

    async def execute(self, command: CreateAnalysisCommand) -> AnalysisStatusDTO:
        log = logger.bind(field_id=command.field_id)

        try:
            validate_geojson_geometry(command.geometry)
        except ValueError as exc:
            raise InvalidGeometryException(str(exc)) from exc

        field = await self._field_repo.get_by_external_id(command.field_id)
        if field is None:
            area_ha = compute_area_hectares(command.geometry)
            field = Field.create(
                external_id=command.field_id,
                geometry=command.geometry,
                area_ha=area_ha,
            )
            field = await self._field_repo.save(field)
            log.info("field_created", field_internal_id=field.id, area_ha=field.area_ha)
        else:
            area_ha = compute_area_hectares(command.geometry)
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
        log.info("analysis_created", analysis_id=analysis.id)

        await self._task_publisher.publish_analysis_job(
            analysis_id=analysis.id,
            field_id=field.id,
            external_field_id=command.field_id,
            geometry=command.geometry,
            requested_metrics=[m.value for m in metrics],
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
        geometry: dict,
        requested_metrics: list[str],
    ) -> None:
        raise NotImplementedError
