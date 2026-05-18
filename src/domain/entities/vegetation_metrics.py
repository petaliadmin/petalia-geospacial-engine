from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from src.domain.value_objects.vegetation_trend import VegetationTrend
from src.domain.value_objects.vegetation_health import VegetationHealth
from src.shared.utils import utcnow


@dataclass
class VegetationMetrics:
    id: str
    analysis_id: str
    ndvi_mean: float
    ndvi_min: float
    ndvi_max: float
    ndvi_std: float
    ndwi_mean: float
    variability_index: float
    trend: VegetationTrend
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def create(
        cls,
        analysis_id: str,
        ndvi_mean: float,
        ndvi_min: float,
        ndvi_max: float,
        ndvi_std: float,
        ndwi_mean: float,
        variability_index: float,
        trend: VegetationTrend,
    ) -> "VegetationMetrics":
        return cls(
            id=str(uuid.uuid4()),
            analysis_id=analysis_id,
            ndvi_mean=round(ndvi_mean, 4),
            ndvi_min=round(ndvi_min, 4),
            ndvi_max=round(ndvi_max, 4),
            ndvi_std=round(ndvi_std, 4),
            ndwi_mean=round(ndwi_mean, 4),
            variability_index=round(variability_index, 4),
            trend=trend,
        )

    @property
    def health(self) -> VegetationHealth:
        return VegetationHealth.from_ndvi(self.ndvi_mean)
