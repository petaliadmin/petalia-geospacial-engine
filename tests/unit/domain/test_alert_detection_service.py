"""Tests for AlertDetectionService — S2-2 new alerts + S1-2 trend.

Covers: WATER_STRESS, NITROGEN_STRESS, HIGH_VARIABILITY detection
and the existing NDVI_LOW/NDVI_DROP alerts.
"""
from unittest.mock import patch

import pytest

from src.domain.services.alert_detection_service import AlertDetectionService
from src.domain.value_objects.alert_type import AlertType
from src.domain.value_objects.alert_severity import AlertSeverity
from tests.conftest import make_metrics


class TestWaterStressAlert:
    """S2-2: WATER_STRESS alert based on NDMI threshold."""

    def test_no_water_stress_when_ndmi_above_threshold(self) -> None:
        metrics = make_metrics(ndmi_mean=0.10)
        service = AlertDetectionService()
        alerts = service._check_water_stress("f1", "a1", metrics)
        assert alerts == []

    def test_water_stress_medium_severity(self) -> None:
        metrics = make_metrics(ndmi_mean=-0.15)
        service = AlertDetectionService()
        alerts = service._check_water_stress("f1", "a1", metrics)
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.WATER_STRESS
        assert alerts[0].severity == AlertSeverity.MEDIUM

    def test_water_stress_high_severity(self) -> None:
        metrics = make_metrics(ndmi_mean=-0.25)
        service = AlertDetectionService()
        alerts = service._check_water_stress("f1", "a1", metrics)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.HIGH

    def test_water_stress_critical_severity(self) -> None:
        metrics = make_metrics(ndmi_mean=-0.40)
        service = AlertDetectionService()
        alerts = service._check_water_stress("f1", "a1", metrics)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_water_stress_message_contains_ndmi_value(self) -> None:
        metrics = make_metrics(ndmi_mean=-0.18)
        service = AlertDetectionService()
        alerts = service._check_water_stress("f1", "a1", metrics)
        assert "NDMI=" in alerts[0].message
        assert "Irrigation" in alerts[0].message


class TestNitrogenStressAlert:
    """S2-2: NITROGEN_STRESS alert based on NDRE threshold."""

    def test_no_nitrogen_stress_above_threshold(self) -> None:
        metrics = make_metrics(ndre_mean=0.35)
        service = AlertDetectionService()
        alerts = service._check_nitrogen_stress("f1", "a1", metrics)
        assert alerts == []

    def test_nitrogen_stress_when_ndre_low(self) -> None:
        metrics = make_metrics(ndre_mean=0.12)
        service = AlertDetectionService()
        alerts = service._check_nitrogen_stress("f1", "a1", metrics)
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.NITROGEN_STRESS
        assert alerts[0].severity == AlertSeverity.MEDIUM

    def test_nitrogen_stress_skipped_when_ndre_none(self) -> None:
        """If NDRE was not computed (pre-S2-1 analysis), no alert must be raised."""
        metrics = make_metrics(ndre_mean=None)
        service = AlertDetectionService()
        alerts = service._check_nitrogen_stress("f1", "a1", metrics)
        assert alerts == []

    def test_nitrogen_stress_message_mentions_foliar(self) -> None:
        metrics = make_metrics(ndre_mean=0.08)
        service = AlertDetectionService()
        alerts = service._check_nitrogen_stress("f1", "a1", metrics)
        assert "foliar" in alerts[0].message.lower() or "Foliar" in alerts[0].message


class TestHighVariabilityAlert:
    """S2-2: HIGH_VARIABILITY alert based on variability_index threshold."""

    def test_no_variability_alert_below_threshold(self) -> None:
        metrics = make_metrics(variability_index=0.15)
        service = AlertDetectionService()
        alerts = service._check_high_variability("f1", "a1", metrics)
        assert alerts == []

    def test_high_variability_alert_above_threshold(self) -> None:
        metrics = make_metrics(variability_index=0.45)
        service = AlertDetectionService()
        alerts = service._check_high_variability("f1", "a1", metrics)
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.HIGH_VARIABILITY
        assert alerts[0].severity == AlertSeverity.LOW

    def test_high_variability_message_mentions_variability(self) -> None:
        metrics = make_metrics(variability_index=0.50)
        service = AlertDetectionService()
        alerts = service._check_high_variability("f1", "a1", metrics)
        assert "VI=" in alerts[0].message


class TestFullDetect:
    """Integration test: detect() aggregates all alert checks."""

    def test_detect_returns_multiple_alerts_simultaneously(self) -> None:
        """Multiple conditions can be true at once — all alerts must be returned."""
        metrics = make_metrics(
            ndvi_mean=0.10,      # NDVI_LOW (critical)
            ndmi_mean=-0.35,     # WATER_STRESS (high)
            ndre_mean=0.05,      # NITROGEN_STRESS (medium)
            variability_index=0.60,  # HIGH_VARIABILITY (low)
        )
        service = AlertDetectionService()
        alerts = service.detect(
            field_id="f1",
            analysis_id="a1",
            current_metrics=metrics,
            cloud_coverage=0.10,
        )
        alert_types = {a.alert_type for a in alerts}
        assert AlertType.NDVI_LOW in alert_types
        assert AlertType.WATER_STRESS in alert_types
        assert AlertType.NITROGEN_STRESS in alert_types
        assert AlertType.HIGH_VARIABILITY in alert_types
