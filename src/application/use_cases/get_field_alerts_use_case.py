import structlog

from src.application.dto.analysis_dto import AlertDTO
from src.application.queries.get_field_alerts_query import GetFieldAlertsQuery
from src.domain.repositories.alert_repository import AbstractAlertRepository
from src.domain.repositories.field_repository import AbstractFieldRepository
from src.shared.exceptions import FieldNotFoundException

logger = structlog.get_logger(__name__)


class GetFieldAlertsUseCase:
    def __init__(
        self,
        field_repo: AbstractFieldRepository,
        alert_repo: AbstractAlertRepository,
    ) -> None:
        self._field_repo = field_repo
        self._alert_repo = alert_repo

    async def execute(self, query: GetFieldAlertsQuery) -> list[AlertDTO]:
        field = await self._field_repo.get_by_external_id(query.field_id)
        if field is None:
            raise FieldNotFoundException(query.field_id)

        alerts = await self._alert_repo.get_by_field_id(
            field.id, limit=query.limit, offset=query.offset
        )
        return [
            AlertDTO(
                id=a.id,
                severity=a.severity,
                alert_type=a.alert_type,
                message=a.message,
                created_at=a.created_at,
            )
            for a in alerts
        ]
