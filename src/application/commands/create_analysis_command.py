from dataclasses import dataclass
from typing import Any

from src.domain.value_objects.requested_metrics import RequestedMetric


@dataclass(frozen=True)
class CreateAnalysisCommand:
    field_id: str
    geometry: dict[str, Any]
    requested_metrics: list[RequestedMetric]
