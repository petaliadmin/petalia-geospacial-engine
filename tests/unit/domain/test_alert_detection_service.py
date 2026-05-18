import pytest
from unittest.mock import patch

from src.domain.entities.vegetation_metrics import VegetationMetrics
from src.domain.services.alert_detection_service import AlertDetectionService
from src.domain.value_objects.alert_severity import AlertSeverity
from src.domain.value_objects.alert_type import AlertType
from src.domain.value_objects.vegetation_trend import VegetationTrend


def _make_metrics(ndvi_mean: float, analysis_id: str = "ana_001") -> VegetationMetrics:
    return VegetationMetrics.create(
        analysis_id=analysis_id,
        ndvi_mean=ndvi_mean,
        ndvi_min=ndvi_mean - 0.1,
        ndvi_max=ndvi_mean + 0.1,
        ndvi_std=0.05,
        ndwi_mean=0.4,
        variability_index=0.1,
        trend=VegetationTrend.STABLE,
    )


@pytest.fixture
def service() -> AlertDetectionService:
    return AlertDetectionService()


def test_no_alerts_for_healthy_field(service):
    metrics = _make_metrics(0.75)
    alerts = service.detect("field_1", "ana_001", metrics, cloud_coverage=0.10)
    assert alerts == []


def test_ndvi_low_alert_medium(service):
    metrics = _make_metrics(0.25)
    alerts = service.detect("field_1", "ana_001", metrics, cloud_coverage=0.10)
    ndvi_alerts = [a for a in alerts if a.alert_type == AlertType.NDVI_LOW]
    assert len(ndvi_alerts) == 1
    assert ndvi_alerts[0].severity == AlertSeverity.MEDIUM


def test_ndvi_low_alert_critical(service):
    metrics = _make_metrics(0.05)
    alerts = service.detect("field_1", "ana_001", metrics, cloud_coverage=0.10)
    ndvi_alerts = [a for a in alerts if a.alert_type == AlertType.NDVI_LOW]
    assert len(ndvi_alerts) == 1
    assert ndvi_alerts[0].severity == AlertSeverity.CRITICAL


def test_cloud_cover_alert(service):
    metrics = _make_metrics(0.75)
    alerts = service.detect("field_1", "ana_001", metrics, cloud_coverage=0.45)
    cloud_alerts = [a for a in alerts if a.alert_type == AlertType.HIGH_CLOUD_COVER]
    assert len(cloud_alerts) == 1
    assert cloud_alerts[0].severity == AlertSeverity.LOW


def test_ndvi_drop_alert(service):
    current = _make_metrics(0.40, "ana_002")
    previous = _make_metrics(0.70, "ana_001")
    alerts = service.detect("field_1", "ana_002", current, cloud_coverage=0.10, previous_metrics=previous)
    drop_alerts = [a for a in alerts if a.alert_type == AlertType.NDVI_DROP]
    assert len(drop_alerts) == 1
    assert drop_alerts[0].severity in (AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL)


def test_no_drop_alert_when_ndvi_improves(service):
    current = _make_metrics(0.70, "ana_002")
    previous = _make_metrics(0.40, "ana_001")
    alerts = service.detect("field_1", "ana_002", current, cloud_coverage=0.10, previous_metrics=previous)
    drop_alerts = [a for a in alerts if a.alert_type == AlertType.NDVI_DROP]
    assert drop_alerts == []
