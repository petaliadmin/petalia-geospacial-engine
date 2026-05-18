from dataclasses import dataclass
from datetime import datetime

from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend


@dataclass
class AnalysisStatusDTO:
    analysis_id: str
    status: AnalysisStatus
    field_id: str
    created_at: datetime


@dataclass
class VegetationDTO:
    mean_ndvi: float
    min_ndvi: float
    max_ndvi: float
    std_ndvi: float
    trend: VegetationTrend
    health: VegetationHealth


@dataclass
class WaterDTO:
    # S1-3: renamed from mean_ndwi to mean_ndmi (formula B8-B11 = NDMI, not NDWI)
    mean_ndmi: float


@dataclass
class VisualizationDTO:
    tile_url: str | None
    thumbnail_url: str | None


@dataclass
class AlertDTO:
    id: str
    severity: AlertSeverity
    alert_type: AlertType
    message: str
    created_at: datetime


@dataclass
class FieldAnalysisDTO:
    field_id: str
    analysis_id: str
    analysis_date: datetime
    status: AnalysisStatus
    vegetation: VegetationDTO | None
    water: WaterDTO | None
    alerts: list[AlertDTO]
    visualization: VisualizationDTO | None
    cloud_coverage: float | None


@dataclass
class TimeseriesEntryDTO:
    """S4-3: Multi-index timeseries entry — includes all vegetation indices."""
    analysis_id: str
    analysis_date: datetime
    ndvi_mean: float
    ndmi_mean: float          # S1-3: was ndwi_mean
    ndre_mean: float | None   # S2-1/S4-3: None for analyses before this feature
    savi_mean: float | None   # S2-1/S4-3
    evi2_mean: float | None   # S2-1/S4-3
    cloud_coverage: float | None
    trend: VegetationTrend
    health: VegetationHealth


@dataclass
class FieldTimeseriesDTO:
    field_id: str
    entries: list[TimeseriesEntryDTO]
    total: int


# -----------------------------------------------------------------------
# S4-1: Batch analysis DTOs
# -----------------------------------------------------------------------

@dataclass
class BatchAnalysisItemDTO:
    field_id: str
    analysis_id: str | None
    status: str
    error: str | None


@dataclass
class BatchAnalysisResultDTO:
    submitted: int
    succeeded: int
    failed: int
    items: list[BatchAnalysisItemDTO]
