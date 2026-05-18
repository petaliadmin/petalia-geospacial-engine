from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.domain.value_objects.vegetation_trend import VegetationTrend
from src.domain.value_objects.vegetation_health import VegetationHealth


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
    tile_url: Optional[str]
    thumbnail_url: Optional[str]


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
    vegetation: Optional[VegetationDTO]
    water: Optional[WaterDTO]
    alerts: list[AlertDTO]
    visualization: Optional[VisualizationDTO]
    cloud_coverage: Optional[float]


@dataclass
class TimeseriesEntryDTO:
    analysis_id: str
    analysis_date: datetime
    ndvi_mean: float
    ndwi_mean: float
    cloud_coverage: Optional[float]
    trend: VegetationTrend
    health: VegetationHealth


@dataclass
class FieldTimeseriesDTO:
    field_id: str
    entries: list[TimeseriesEntryDTO]
    total: int
