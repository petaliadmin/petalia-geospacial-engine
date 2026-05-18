from abc import ABC, abstractmethod
from typing import Any


class AbstractCacheService(ABC):
    @abstractmethod
    async def get_latest(self, field_id: str) -> Any | None: ...

    @abstractmethod
    async def set_latest(self, field_id: str, data: Any) -> None: ...

    @abstractmethod
    async def get_timeseries(self, field_id: str) -> Any | None: ...

    @abstractmethod
    async def set_timeseries(self, field_id: str, data: Any) -> None: ...

    @abstractmethod
    async def get_tiles(self, field_id: str) -> str | None: ...

    @abstractmethod
    async def set_tiles(self, field_id: str, tile_url: str) -> None: ...

    @abstractmethod
    async def get_thumbnail(self, field_id: str) -> str | None: ...

    @abstractmethod
    async def set_thumbnail(self, field_id: str, thumbnail_url: str) -> None: ...

    @abstractmethod
    async def get_analysis(self, analysis_id: str) -> Any | None: ...

    @abstractmethod
    async def set_analysis(self, analysis_id: str, data: Any) -> None: ...

    @abstractmethod
    async def invalidate_field(self, field_id: str) -> None: ...
