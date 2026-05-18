from abc import ABC, abstractmethod
from typing import Optional

from src.domain.entities.analysis import Analysis
from src.domain.value_objects.analysis_status import AnalysisStatus


class AbstractAnalysisRepository(ABC):
    @abstractmethod
    async def get_by_id(self, analysis_id: str) -> Optional[Analysis]: ...

    @abstractmethod
    async def get_latest_for_field(self, field_id: str) -> Optional[Analysis]: ...

    @abstractmethod
    async def list_for_field(
        self,
        field_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Analysis]: ...

    @abstractmethod
    async def get_running_for_field(self, field_id: str) -> Optional[Analysis]: ...

    @abstractmethod
    async def save(self, analysis: Analysis) -> Analysis: ...

    @abstractmethod
    async def update(self, analysis: Analysis) -> Analysis: ...
