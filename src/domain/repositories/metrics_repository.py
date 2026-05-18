from abc import ABC, abstractmethod

from src.domain.entities.vegetation_metrics import VegetationMetrics


class AbstractMetricsRepository(ABC):
    @abstractmethod
    async def get_by_analysis_id(self, analysis_id: str) -> VegetationMetrics | None: ...

    @abstractmethod
    async def get_timeseries_for_field(
        self,
        field_id: str,
        limit: int = 30,
    ) -> list[VegetationMetrics]: ...

    @abstractmethod
    async def save(self, metrics: VegetationMetrics) -> VegetationMetrics: ...
