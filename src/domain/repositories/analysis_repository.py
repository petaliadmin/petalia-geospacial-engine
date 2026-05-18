from abc import ABC, abstractmethod

from src.domain.entities.analysis import Analysis


class AbstractAnalysisRepository(ABC):
    @abstractmethod
    async def get_by_id(self, analysis_id: str) -> Analysis | None: ...

    @abstractmethod
    async def get_latest_for_field(self, field_id: str) -> Analysis | None: ...

    @abstractmethod
    async def list_for_field(
        self,
        field_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Analysis]: ...

    @abstractmethod
    async def get_running_for_field(self, field_id: str) -> Analysis | None: ...

    @abstractmethod
    async def save(self, analysis: Analysis) -> Analysis: ...

    @abstractmethod
    async def update(self, analysis: Analysis) -> Analysis: ...
