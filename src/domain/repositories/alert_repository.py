from abc import ABC, abstractmethod

from src.domain.entities.agronomic_alert import AgronomicAlert


class AbstractAlertRepository(ABC):
    @abstractmethod
    async def get_by_field_id(
        self,
        field_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgronomicAlert]: ...

    @abstractmethod
    async def get_by_analysis_id(self, analysis_id: str) -> list[AgronomicAlert]: ...

    @abstractmethod
    async def save_many(self, alerts: list[AgronomicAlert]) -> list[AgronomicAlert]: ...
