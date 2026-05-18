from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend


class CreateAnalysisRequest(BaseModel):
    fieldId: str = Field(..., min_length=1, max_length=255, description="External field identifier")
    geometry: dict[str, Any] = Field(..., description="GeoJSON geometry of the field")
    requestedMetrics: list[RequestedMetric] = Field(
        default=[
            RequestedMetric.NDVI,
            RequestedMetric.NDWI,
            RequestedMetric.CLOUD,
            RequestedMetric.TILES,
            RequestedMetric.ALERTS,
        ],
        description="List of metrics to compute",
    )

    @field_validator("geometry")
    @classmethod
    def validate_geometry_type(cls, v: dict) -> dict:
        if "type" not in v:
            raise ValueError("Geometry must have a 'type' field")
        return v


class CreateAnalysisResponse(BaseModel):
    analysisId: str
    status: AnalysisStatus
    fieldId: str
    createdAt: datetime

    model_config = {"from_attributes": True}


class VegetationResponse(BaseModel):
    meanNdvi: float
    minNdvi: float
    maxNdvi: float
    stdNdvi: float
    trend: VegetationTrend
    health: VegetationHealth


class WaterResponse(BaseModel):
    meanNdwi: float


class VisualizationResponse(BaseModel):
    tileUrl: Optional[str]
    thumbnailUrl: Optional[str]


class AlertResponse(BaseModel):
    id: str
    severity: AlertSeverity
    alertType: AlertType
    message: str
    createdAt: datetime


class AnalysisDetailResponse(BaseModel):
    fieldId: str
    analysisId: str
    analysisDate: datetime
    status: AnalysisStatus
    vegetation: Optional[VegetationResponse] = None
    water: Optional[WaterResponse] = None
    alerts: list[AlertResponse] = []
    visualization: Optional[VisualizationResponse] = None
    cloudCoverage: Optional[float] = None
