from datetime import datetime

from pydantic import BaseModel

from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend


class TimeseriesEntryResponse(BaseModel):
    """S4-3: Multi-index timeseries entry.
    S1-3: ndwiMean → ndmiMean (formula B8-B11 = NDMI not NDWI).
    """

    analysisId: str  # noqa: N815
    analysisDate: datetime  # noqa: N815
    ndviMean: float  # noqa: N815
    ndmiMean: float  # noqa: N815
    ndreMean: float | None = None  # noqa: N815
    saviMean: float | None = None  # noqa: N815
    evi2Mean: float | None = None  # noqa: N815
    cloudCoverage: float | None = None  # noqa: N815
    trend: VegetationTrend
    health: VegetationHealth


class FieldTimeseriesResponse(BaseModel):
    fieldId: str  # noqa: N815
    total: int
    entries: list[TimeseriesEntryResponse]


class TileInfoResponse(BaseModel):
    fieldId: str  # noqa: N815
    tileUrl: str | None = None  # noqa: N815
    thumbnailUrl: str | None = None  # noqa: N815


class AlertListResponse(BaseModel):
    fieldId: str  # noqa: N815
    total: int
    alerts: list[dict]
