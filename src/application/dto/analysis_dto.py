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
    mean_ndwi: float


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
    analysis_id: str
    analysis_date: datetime
    ndvi_mean: float
    ndwi_mean: float
    cloud_coverage: float | None
    trend: VegetationTrend
    health: VegetationHealth


@dataclass
class FieldTimeseriesDTO:
    field_id: str
    entries: list[TimeseriesEntryDTO]
    total: int
