from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid

from src.shared.utils import utcnow


@dataclass
class Field:
    id: str
    external_id: str
    geometry: dict[str, Any]
    area_ha: float
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @classmethod
    def create(cls, external_id: str, geometry: dict[str, Any], area_ha: float) -> "Field":
        return cls(
            id=str(uuid.uuid4()),
            external_id=external_id,
            geometry=geometry,
            area_ha=area_ha,
        )

    def update_geometry(self, geometry: dict[str, Any], area_ha: float) -> None:
        self.geometry = geometry
        self.area_ha = area_ha
        self.updated_at = utcnow()
