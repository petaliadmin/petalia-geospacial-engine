from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.agronomic_alert import AgronomicAlert
from src.domain.repositories.alert_repository import AbstractAlertRepository
from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.infrastructure.database.models import AgronomicAlertModel


class SQLAlertRepository(AbstractAlertRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_field_id(
        self, field_id: str, limit: int = 50, offset: int = 0
    ) -> list[AgronomicAlert]:
        result = await self._session.execute(
            select(AgronomicAlertModel)
            .where(AgronomicAlertModel.field_id == field_id)
            .order_by(AgronomicAlertModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_analysis_id(self, analysis_id: str) -> list[AgronomicAlert]:
        result = await self._session.execute(
            select(AgronomicAlertModel).where(
                AgronomicAlertModel.analysis_id == analysis_id
            )
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def save_many(self, alerts: list[AgronomicAlert]) -> list[AgronomicAlert]:
        models = [
            AgronomicAlertModel(
                id=a.id,
                field_id=a.field_id,
                analysis_id=a.analysis_id,
                severity=a.severity.value,
                alert_type=a.alert_type.value,
                message=a.message,
                created_at=a.created_at,
            )
            for a in alerts
        ]
        self._session.add_all(models)
        await self._session.flush()
        return alerts

    @staticmethod
    def _to_entity(model: AgronomicAlertModel) -> AgronomicAlert:
        return AgronomicAlert(
            id=model.id,
            field_id=model.field_id,
            analysis_id=model.analysis_id,
            severity=AlertSeverity(model.severity),
            alert_type=AlertType(model.alert_type),
            message=model.message,
            created_at=model.created_at,
        )
