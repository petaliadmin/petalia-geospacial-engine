from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend


class CreateAnalysisRequest(BaseModel):
    fieldId: str = Field(..., min_length=1, max_length=255, description="External field identifier")  # noqa: N815
    geometry: dict[str, Any] = Field(..., description="GeoJSON geometry of the field")
    requestedMetrics: list[RequestedMetric] = Field(  # noqa: N815
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
    analysisId: str  # noqa: N815
    status: AnalysisStatus
    fieldId: str  # noqa: N815
    createdAt: datetime  # noqa: N815

    model_config = {"from_attributes": True}


class VegetationResponse(BaseModel):
    meanNdvi: float  # noqa: N815
    minNdvi: float  # noqa: N815
    maxNdvi: float  # noqa: N815
    stdNdvi: float  # noqa: N815
    ndreMean: float | None = None  # noqa: N815  S2-1
    saviMean: float | None = None  # noqa: N815  S2-1
    evi2Mean: float | None = None  # noqa: N815  S2-1
    trend: VegetationTrend
    health: VegetationHealth


class WaterResponse(BaseModel):
    # S1-3: renamed from meanNdwi — (B8-B11)/(B8+B11) is NDMI not NDWI
    meanNdmi: float  # noqa: N815


class VisualizationResponse(BaseModel):
    tileUrl: str | None  # noqa: N815
    thumbnailUrl: str | None  # noqa: N815


class AlertResponse(BaseModel):
    id: str
    severity: AlertSeverity
    alertType: AlertType  # noqa: N815
    message: str
    createdAt: datetime  # noqa: N815


class AnalysisDetailResponse(BaseModel):
    fieldId: str  # noqa: N815
    analysisId: str  # noqa: N815
    analysisDate: datetime  # noqa: N815
    status: AnalysisStatus
    vegetation: VegetationResponse | None = None
    water: WaterResponse | None = None
    alerts: list[AlertResponse] = []
    visualization: VisualizationResponse | None = None
    cloudCoverage: float | None = None  # noqa: N815


# -----------------------------------------------------------------------
# S4-3: Multi-index timeseries response schema
# -----------------------------------------------------------------------

class TimeseriesEntryResponse(BaseModel):
    """S4-3: Timeseries entry with all vegetation indices."""
    analysisId: str          # noqa: N815
    analysisDate: datetime   # noqa: N815
    ndviMean: float          # noqa: N815
    ndmiMean: float          # noqa: N815  S1-3: was ndwiMean
    ndreMean: float | None = None  # noqa: N815  S2-1/S4-3
    saviMean: float | None = None  # noqa: N815  S2-1/S4-3
    evi2Mean: float | None = None  # noqa: N815  S2-1/S4-3
    cloudCoverage: float | None = None  # noqa: N815
    trend: VegetationTrend
    health: VegetationHealth


class FieldTimeseriesResponse(BaseModel):
    fieldId: str  # noqa: N815
    total: int
    entries: list[TimeseriesEntryResponse]


# -----------------------------------------------------------------------
# S4-1: Batch analysis request/response schemas
# -----------------------------------------------------------------------

class BatchAnalysisRequest(BaseModel):
    """S4-1: Submit up to 50 field analyses in a single request.

    Each field is processed independently in parallel via Celery group().
    Partial failures are reported per-field in the response.
    """
    fields: list[CreateAnalysisRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of field analyses to submit (max 50)",
    )


class BatchAnalysisItemResponse(BaseModel):
    fieldId: str  # noqa: N815
    analysisId: str | None = None  # noqa: N815
    status: str
    error: str | None = None


class BatchAnalysisResponse(BaseModel):
    submitted: int
    succeeded: int
    failed: int
    items: list[BatchAnalysisItemResponse]
