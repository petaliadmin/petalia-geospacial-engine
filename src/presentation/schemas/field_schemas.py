from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend


class TimeseriesEntryResponse(BaseModel):
    analysisId: str
    analysisDate: datetime
    ndviMean: float
    ndwiMean: float
    cloudCoverage: Optional[float] = None
    trend: VegetationTrend
    health: VegetationHealth


class FieldTimeseriesResponse(BaseModel):
    fieldId: str
    total: int
    entries: list[TimeseriesEntryResponse]


class TileInfoResponse(BaseModel):
    fieldId: str
    tileUrl: Optional[str] = None
    thumbnailUrl: Optional[str] = None


class AlertListResponse(BaseModel):
    fieldId: str
    total: int
    alerts: list[dict]
