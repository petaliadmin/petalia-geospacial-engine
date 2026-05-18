from typing import Optional

from src.domain.entities.agronomic_alert import AgronomicAlert
from src.domain.entities.vegetation_metrics import VegetationMetrics
from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.shared.config import get_settings


class AlertDetectionService:
    """Domain service that encapsulates agronomic alert detection rules."""

    def __init__(self) -> None:
        settings = get_settings()
        self._ndvi_low_threshold = settings.ndvi_low_threshold
        self._ndvi_drop_threshold = settings.ndvi_drop_threshold
        self._cloud_cover_threshold = settings.cloud_cover_threshold

    def detect(
        self,
        field_id: str,
        analysis_id: str,
        current_metrics: VegetationMetrics,
        cloud_coverage: float,
        previous_metrics: Optional[VegetationMetrics] = None,
    ) -> list[AgronomicAlert]:
        alerts: list[AgronomicAlert] = []

        alerts.extend(self._check_ndvi_low(field_id, analysis_id, current_metrics))
        alerts.extend(self._check_cloud_cover(field_id, analysis_id, cloud_coverage))

        if previous_metrics is not None:
            alerts.extend(
                self._check_ndvi_drop(field_id, analysis_id, current_metrics, previous_metrics)
            )

        return alerts

    def _check_ndvi_low(
        self,
        field_id: str,
        analysis_id: str,
        metrics: VegetationMetrics,
    ) -> list[AgronomicAlert]:
        if metrics.ndvi_mean >= self._ndvi_low_threshold:
            return []

        severity = (
            AlertSeverity.CRITICAL if metrics.ndvi_mean < 0.10
            else AlertSeverity.HIGH if metrics.ndvi_mean < 0.20
            else AlertSeverity.MEDIUM
        )
        return [
            AgronomicAlert.create(
                field_id=field_id,
                analysis_id=analysis_id,
                severity=severity,
                alert_type=AlertType.NDVI_LOW,
                message=(
                    f"NDVI mean ({metrics.ndvi_mean:.2f}) is below the critical threshold "
                    f"of {self._ndvi_low_threshold}. Vegetation health is compromised."
                ),
            )
        ]

    def _check_ndvi_drop(
        self,
        field_id: str,
        analysis_id: str,
        current: VegetationMetrics,
        previous: VegetationMetrics,
    ) -> list[AgronomicAlert]:
        if previous.ndvi_mean == 0:
            return []

        drop_pct = (previous.ndvi_mean - current.ndvi_mean) / previous.ndvi_mean
        if drop_pct <= self._ndvi_drop_threshold:
            return []

        severity = (
            AlertSeverity.CRITICAL if drop_pct > 0.50
            else AlertSeverity.HIGH if drop_pct > 0.35
            else AlertSeverity.MEDIUM
        )
        return [
            AgronomicAlert.create(
                field_id=field_id,
                analysis_id=analysis_id,
                severity=severity,
                alert_type=AlertType.NDVI_DROP,
                message=(
                    f"NDVI dropped by {drop_pct * 100:.1f}% compared to previous analysis "
                    f"({previous.ndvi_mean:.2f} → {current.ndvi_mean:.2f}). "
                    "Possible crop stress or damage detected."
                ),
            )
        ]

    def _check_cloud_cover(
        self,
        field_id: str,
        analysis_id: str,
        cloud_coverage: float,
    ) -> list[AgronomicAlert]:
        if cloud_coverage <= self._cloud_cover_threshold:
            return []

        severity = (
            AlertSeverity.HIGH if cloud_coverage > 0.70
            else AlertSeverity.MEDIUM if cloud_coverage > 0.50
            else AlertSeverity.LOW
        )
        return [
            AgronomicAlert.create(
                field_id=field_id,
                analysis_id=analysis_id,
                severity=severity,
                alert_type=AlertType.HIGH_CLOUD_COVER,
                message=(
                    f"Cloud coverage ({cloud_coverage * 100:.1f}%) exceeds the threshold "
                    f"of {self._cloud_cover_threshold * 100:.0f}%. "
                    "Analysis accuracy may be reduced."
                ),
            )
        ]
