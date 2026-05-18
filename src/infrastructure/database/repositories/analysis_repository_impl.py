from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.analysis import Analysis
from src.domain.repositories.analysis_repository import AbstractAnalysisRepository
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.infrastructure.database.models import AnalysisModel


class SQLAnalysisRepository(AbstractAnalysisRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, analysis_id: str) -> Optional[Analysis]:
        result = await self._session.execute(
            select(AnalysisModel).where(AnalysisModel.id == analysis_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_latest_for_field(self, field_id: str) -> Optional[Analysis]:
        result = await self._session.execute(
            select(AnalysisModel)
            .where(
                AnalysisModel.field_id == field_id,
                AnalysisModel.status == AnalysisStatus.COMPLETED,
            )
            .order_by(AnalysisModel.completed_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_for_field(
        self, field_id: str, limit: int = 50, offset: int = 0
    ) -> list[Analysis]:
        result = await self._session.execute(
            select(AnalysisModel)
            .where(
                AnalysisModel.field_id == field_id,
                AnalysisModel.status == AnalysisStatus.COMPLETED,
            )
            .order_by(AnalysisModel.completed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_running_for_field(self, field_id: str) -> Optional[Analysis]:
        result = await self._session.execute(
            select(AnalysisModel)
            .where(
                AnalysisModel.field_id == field_id,
                AnalysisModel.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING]),
            )
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, analysis: Analysis) -> Analysis:
        model = AnalysisModel(
            id=analysis.id,
            field_id=analysis.field_id,
            status=analysis.status.value,
            requested_metrics=[m.value for m in analysis.requested_metrics],
            algorithm_version=analysis.algorithm_version,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
            error_message=analysis.error_message,
        )
        self._session.add(model)
        await self._session.flush()
        return analysis

    async def update(self, analysis: Analysis) -> Analysis:
        result = await self._session.execute(
            select(AnalysisModel).where(AnalysisModel.id == analysis.id)
        )
        model = result.scalar_one()
        model.status = analysis.status.value
        model.completed_at = analysis.completed_at
        model.error_message = analysis.error_message
        await self._session.flush()
        return analysis

    @staticmethod
    def _to_entity(model: AnalysisModel) -> Analysis:
        return Analysis(
            id=model.id,
            field_id=model.field_id,
            status=AnalysisStatus(model.status),
            requested_metrics=[RequestedMetric(m) for m in model.requested_metrics],
            algorithm_version=model.algorithm_version,
            created_at=model.created_at,
            completed_at=model.completed_at,
            error_message=model.error_message,
        )
