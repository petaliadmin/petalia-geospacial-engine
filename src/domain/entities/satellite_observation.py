import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.shared.utils import utcnow


@dataclass
class SatelliteObservation:
    id: str
    analysis_id: str
    acquisition_date: datetime
    cloud_coverage: float
    image_source: str
    scene_id: str | None = None
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def create(
        cls,
        analysis_id: str,
        acquisition_date: datetime,
        cloud_coverage: float,
        image_source: str,
        scene_id: str | None = None,
    ) -> "SatelliteObservation":
        return cls(
            id=str(uuid.uuid4()),
            analysis_id=analysis_id,
            acquisition_date=acquisition_date,
            cloud_coverage=cloud_coverage,
            image_source=image_source,
            scene_id=scene_id,
        )

    @property
    def has_acceptable_cloud_cover(self) -> bool:
        return self.cloud_coverage <= 0.30
