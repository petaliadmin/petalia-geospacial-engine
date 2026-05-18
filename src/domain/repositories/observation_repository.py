from abc import ABC, abstractmethod

from src.domain.entities.satellite_observation import SatelliteObservation


class AbstractObservationRepository(ABC):
    @abstractmethod
    async def get_by_analysis_id(self, analysis_id: str) -> SatelliteObservation | None: ...

    @abstractmethod
    async def save(self, observation: SatelliteObservation) -> SatelliteObservation: ...
