from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.satellite_observation import SatelliteObservation
from src.domain.repositories.observation_repository import AbstractObservationRepository
from src.infrastructure.database.models import SatelliteObservationModel


class SQLObservationRepository(AbstractObservationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_analysis_id(self, analysis_id: str) -> Optional[SatelliteObservation]:
        result = await self._session.execute(
            select(SatelliteObservationModel).where(
                SatelliteObservationModel.analysis_id == analysis_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, observation: SatelliteObservation) -> SatelliteObservation:
        model = SatelliteObservationModel(
            id=observation.id,
            analysis_id=observation.analysis_id,
            acquisition_date=observation.acquisition_date,
            cloud_coverage=observation.cloud_coverage,
            image_source=observation.image_source,
            scene_id=observation.scene_id,
            created_at=observation.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return observation

    @staticmethod
    def _to_entity(model: SatelliteObservationModel) -> SatelliteObservation:
        return SatelliteObservation(
            id=model.id,
            analysis_id=model.analysis_id,
            acquisition_date=model.acquisition_date,
            cloud_coverage=model.cloud_coverage,
            image_source=model.image_source,
            scene_id=model.scene_id,
            created_at=model.created_at,
        )
