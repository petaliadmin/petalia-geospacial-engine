from dataclasses import dataclass
from typing import Any

from src.shared.exceptions import InvalidGeometryException
from src.shared.utils import compute_area_hectares, validate_geojson_geometry


@dataclass(frozen=True)
class Geometry:
    geojson: dict[str, Any]
    area_ha: float

    @classmethod
    def from_geojson(cls, geojson: dict[str, Any]) -> "Geometry":
        try:
            validate_geojson_geometry(geojson)
        except ValueError as exc:
            raise InvalidGeometryException(str(exc)) from exc
        area_ha = compute_area_hectares(geojson)
        return cls(geojson=geojson, area_ha=area_ha)

    def __str__(self) -> str:
        return f"Geometry(type={self.geojson.get('type')}, area_ha={self.area_ha})"
