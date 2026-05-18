
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.field import Field
from src.domain.repositories.field_repository import AbstractFieldRepository
from src.infrastructure.database.models import FieldModel


class SQLFieldRepository(AbstractFieldRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, field_id: str) -> Field | None:
        result = await self._session.execute(
            select(FieldModel).where(FieldModel.id == field_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_external_id(self, external_id: str) -> Field | None:
        result = await self._session.execute(
            select(FieldModel).where(FieldModel.external_id == external_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, field: Field) -> Field:
        model = FieldModel(
            id=field.id,
            external_id=field.external_id,
            geometry=field.geometry,
            area_ha=field.area_ha,
            created_at=field.created_at,
            updated_at=field.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return field

    async def update(self, field: Field) -> Field:
        result = await self._session.execute(
            select(FieldModel).where(FieldModel.id == field.id)
        )
        model = result.scalar_one()
        model.geometry = field.geometry
        model.area_ha = field.area_ha
        model.updated_at = field.updated_at
        await self._session.flush()
        return field

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Field]:
        result = await self._session.execute(
            select(FieldModel).limit(limit).offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(model: FieldModel) -> Field:
        return Field(
            id=model.id,
            external_id=model.external_id,
            geometry=model.geometry,
            area_ha=model.area_ha,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
