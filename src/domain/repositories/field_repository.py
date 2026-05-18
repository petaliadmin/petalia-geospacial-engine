from abc import ABC, abstractmethod
from typing import Optional

from src.domain.entities.field import Field


class AbstractFieldRepository(ABC):
    @abstractmethod
    async def get_by_id(self, field_id: str) -> Optional[Field]: ...

    @abstractmethod
    async def get_by_external_id(self, external_id: str) -> Optional[Field]: ...

    @abstractmethod
    async def save(self, field: Field) -> Field: ...

    @abstractmethod
    async def update(self, field: Field) -> Field: ...

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Field]: ...
