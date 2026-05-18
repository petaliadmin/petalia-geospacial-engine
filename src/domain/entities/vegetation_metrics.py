import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend
from src.shared.utils import utcnow


@dataclass
class VegetationMetrics:
    """Domain entity representing the computed vegetation metrics for one analysis.

    S1-2: `trend` is now computed externally by AlertDetectionService, comparing
          current vs. previous metrics. It is stored in the entity but NOT derived
          from a single image's statistics.
    S1-3: `ndwi_mean` → `ndmi_mean` — the formula (B8-B11)/(B8+B11) yields NDMI
          (Gao 1996, moisture stress index), not NDWI (McFeeters 1996, open water).
    S2-1: Added ndre_mean, savi_mean, evi2_mean — optional, None when not computed.
    """
    id: str
    analysis_id: str
    ndvi_mean: float
    ndvi_min: float
    ndvi_max: float
    ndvi_std: float
    ndmi_mean: float          # S1-3: formerly ndwi_mean
    ndre_mean: float | None   # S2-1: Red-Edge, None when not requested
    savi_mean: float | None   # S2-1: Soil-Adjusted, None when not requested
    evi2_mean: float | None   # S2-1: Enhanced VI, None when not requested
    variability_index: float
    trend: VegetationTrend    # S1-2: set by AlertDetectionService, not from single image
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def create(
        cls,
        analysis_id: str,
        ndvi_mean: float,
        ndvi_min: float,
        ndvi_max: float,
        ndvi_std: float,
        ndmi_mean: float,
        variability_index: float,
        trend: VegetationTrend,
        ndre_mean: float | None = None,
        savi_mean: float | None = None,
        evi2_mean: float | None = None,
    ) -> "VegetationMetrics":
        return cls(
            id=str(uuid.uuid4()),
            analysis_id=analysis_id,
            ndvi_mean=round(ndvi_mean, 4),
            ndvi_min=round(ndvi_min, 4),
            ndvi_max=round(ndvi_max, 4),
            ndvi_std=round(ndvi_std, 4),
            ndmi_mean=round(ndmi_mean, 4),
            ndre_mean=round(ndre_mean, 4) if ndre_mean is not None else None,
            savi_mean=round(savi_mean, 4) if savi_mean is not None else None,
            evi2_mean=round(evi2_mean, 4) if evi2_mean is not None else None,
            variability_index=round(variability_index, 4),
            trend=trend,
        )

    @property
    def health(self) -> VegetationHealth:
        return VegetationHealth.from_ndvi(self.ndvi_mean)
