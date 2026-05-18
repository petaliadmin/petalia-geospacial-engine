from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.shared.utils import utcnow


@dataclass
class Analysis:
    id: str
    field_id: str
    status: AnalysisStatus
    requested_metrics: list[RequestedMetric]
    algorithm_version: str
    created_at: datetime = field(default_factory=utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    @classmethod
    def create(
        cls,
        field_id: str,
        requested_metrics: list[RequestedMetric],
        algorithm_version: str = "1.0.0",
    ) -> "Analysis":
        return cls(
            id=f"ana_{uuid.uuid4().hex[:12]}",
            field_id=field_id,
            status=AnalysisStatus.PENDING,
            requested_metrics=requested_metrics,
            algorithm_version=algorithm_version,
        )

    def mark_running(self) -> None:
        self.status = AnalysisStatus.RUNNING

    def mark_completed(self) -> None:
        self.status = AnalysisStatus.COMPLETED
        self.completed_at = utcnow()

    def mark_failed(self, error_message: str) -> None:
        self.status = AnalysisStatus.FAILED
        self.error_message = error_message
        self.completed_at = utcnow()

    @property
    def is_terminal(self) -> bool:
        return self.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED)
