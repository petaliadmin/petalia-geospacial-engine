from datetime import date

from src.domain.entities.agronomic_alert import AgronomicAlert
from src.domain.entities.vegetation_metrics import VegetationMetrics
from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.domain.value_objects.vegetation_trend import VegetationTrend
from src.shared.config import get_settings

# S4-4: Phenological thresholds — NDVI low threshold varies by growing stage.
# A NDVI of 0.25 is normal at germination (March) but critical in peak season (July).
PHENOLOGY_THRESHOLDS: dict[str, dict] = {
    "early_season": {"doy_range": (60, 150), "ndvi_low": 0.15},    # Mar–May: seedling stage
    "peak_season":  {"doy_range": (150, 240), "ndvi_low": 0.40},   # Jun–Aug: full canopy
    "late_season":  {"doy_range": (240, 330), "ndvi_low": 0.20},   # Sep–Nov: senescence
}


class AlertDetectionService:
    """Domain service that encapsulates agronomic alert detection rules.

    S1-2: `_compute_trend()` now performs a real temporal comparison between
          current and previous VegetationMetrics, rather than classifying a
          single image's NDVI value.
    S2-2: Added WATER_STRESS (NDMI), NITROGEN_STRESS (NDRE), HIGH_VARIABILITY.
    S4-4: NDVI low threshold is phenologically adapted to the day of year.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._ndvi_drop_threshold = settings.ndvi_drop_threshold
        self._cloud_cover_threshold = settings.cloud_cover_threshold
        self._ndmi_stress_threshold = settings.ndmi_stress_threshold
        self._ndre_low_threshold = settings.ndre_low_threshold
        self._variability_high_threshold = settings.variability_high_threshold
        self._ndvi_low_threshold_default = settings.ndvi_low_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        field_id: str,
        analysis_id: str,
        current_metrics: VegetationMetrics,
        cloud_coverage: float,
        previous_metrics: VegetationMetrics | None = None,
    ) -> list[AgronomicAlert]:
        """Detect all applicable agronomic alerts for the current analysis."""
        alerts: list[AgronomicAlert] = []

        alerts.extend(self._check_ndvi_low(field_id, analysis_id, current_metrics))
        alerts.extend(self._check_cloud_cover(field_id, analysis_id, cloud_coverage))
        alerts.extend(self._check_water_stress(field_id, analysis_id, current_metrics))
        alerts.extend(self._check_nitrogen_stress(field_id, analysis_id, current_metrics))
        alerts.extend(self._check_high_variability(field_id, analysis_id, current_metrics))

        if previous_metrics is not None:
            alerts.extend(
                self._check_ndvi_drop(field_id, analysis_id, current_metrics, previous_metrics)
            )

        return alerts

    @staticmethod
    def compute_trend(
        current: VegetationMetrics,
        previous: VegetationMetrics | None,
    ) -> VegetationTrend:
        """S1-2: Compute real vegetation trend based on NDVI delta between two analyses.

        Requires at least two observations. A delta > +0.05 is classified as UP,
        < -0.05 as DOWN, otherwise STABLE. The ±0.05 margin avoids false positives
        from sensor noise between adjacent acquisition dates.
        """
        if previous is None:
            return VegetationTrend.STABLE  # insufficient data for trend

        delta = current.ndvi_mean - previous.ndvi_mean
        if delta > 0.05:
            return VegetationTrend.UP
        if delta < -0.05:
            return VegetationTrend.DOWN
        return VegetationTrend.STABLE

    # ------------------------------------------------------------------
    # Private checks
    # ------------------------------------------------------------------

    def _get_seasonal_ndvi_threshold(self) -> float:
        """S4-4: Return the NDVI low threshold appropriate for the current day of year."""
        doy = date.today().timetuple().tm_yday
        for _period, config in PHENOLOGY_THRESHOLDS.items():
            low, high = config["doy_range"]
            if low <= doy <= high:
                return config["ndvi_low"]
        return self._ndvi_low_threshold_default

    def _check_ndvi_low(
        self,
        field_id: str,
        analysis_id: str,
        metrics: VegetationMetrics,
    ) -> list[AgronomicAlert]:
        # S4-4: use phenologically-adapted threshold
        threshold = self._get_seasonal_ndvi_threshold()
        if metrics.ndvi_mean >= threshold:
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
                    f"NDVI mean ({metrics.ndvi_mean:.2f}) is below the seasonal threshold "
                    f"of {threshold:.2f}. Vegetation health is compromised."
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

    def _check_water_stress(
        self,
        field_id: str,
        analysis_id: str,
        metrics: VegetationMetrics,
    ) -> list[AgronomicAlert]:
        """S2-2: NDMI < threshold indicates significant leaf water content deficit."""
        if metrics.ndmi_mean is None or metrics.ndmi_mean >= self._ndmi_stress_threshold:
            return []

        severity = (
            AlertSeverity.CRITICAL if metrics.ndmi_mean < -0.30
            else AlertSeverity.HIGH if metrics.ndmi_mean < -0.20
            else AlertSeverity.MEDIUM
        )
        return [
            AgronomicAlert.create(
                field_id=field_id,
                analysis_id=analysis_id,
                severity=severity,
                alert_type=AlertType.WATER_STRESS,
                message=(
                    f"Water stress detected (NDMI={metrics.ndmi_mean:.2f}). "
                    "Leaf water content is significantly below normal. "
                    "Irrigation is recommended."
                ),
            )
        ]

    def _check_nitrogen_stress(
        self,
        field_id: str,
        analysis_id: str,
        metrics: VegetationMetrics,
    ) -> list[AgronomicAlert]:
        """S2-2: NDRE < threshold indicates possible chlorophyll/nitrogen deficiency.

        NDRE is sensitive to chlorophyll changes 2-3 weeks before NDVI detects them,
        making early intervention possible.
        """
        if metrics.ndre_mean is None or metrics.ndre_mean >= self._ndre_low_threshold:
            return []

        return [
            AgronomicAlert.create(
                field_id=field_id,
                analysis_id=analysis_id,
                severity=AlertSeverity.MEDIUM,
                alert_type=AlertType.NITROGEN_STRESS,
                message=(
                    f"Possible nitrogen / chlorophyll deficiency (NDRE={metrics.ndre_mean:.2f}). "
                    f"Threshold is {self._ndre_low_threshold:.2f}. "
                    "Foliar analysis is recommended."
                ),
            )
        ]

    def _check_high_variability(
        self,
        field_id: str,
        analysis_id: str,
        metrics: VegetationMetrics,
    ) -> list[AgronomicAlert]:
        """S2-2: High intra-field NDVI variability suggests heterogeneous field conditions."""
        if metrics.variability_index <= self._variability_high_threshold:
            return []

        return [
            AgronomicAlert.create(
                field_id=field_id,
                analysis_id=analysis_id,
                severity=AlertSeverity.LOW,
                alert_type=AlertType.HIGH_VARIABILITY,
                message=(
                    f"High intra-field variability detected (VI={metrics.variability_index:.2f}). "
                    "Some zones may have soil, drainage, or pest issues. "
                    "Variable-rate application zoning is recommended."
                ),
            )
        ]
