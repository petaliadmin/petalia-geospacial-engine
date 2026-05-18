from dataclasses import dataclass, field
from datetime import datetime
import uuid

from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.shared.utils import utcnow


@dataclass
class AgronomicAlert:
    id: str
    field_id: str
    analysis_id: str
    severity: AlertSeverity
    alert_type: AlertType
    message: str
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def create(
        cls,
        field_id: str,
        analysis_id: str,
        severity: AlertSeverity,
        alert_type: AlertType,
        message: str,
    ) -> "AgronomicAlert":
        return cls(
            id=f"alt_{uuid.uuid4().hex[:12]}",
            field_id=field_id,
            analysis_id=analysis_id,
            severity=severity,
            alert_type=alert_type,
            message=message,
        )
