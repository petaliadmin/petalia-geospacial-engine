import pytest

from src.domain.entities.vegetation_metrics import VegetationMetrics
from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend


def _make(ndvi_mean: float) -> VegetationMetrics:
    return VegetationMetrics.create(
        analysis_id="ana_001",
        ndvi_mean=ndvi_mean,
        ndvi_min=ndvi_mean - 0.1,
        ndvi_max=ndvi_mean + 0.1,
        ndvi_std=0.05,
        ndwi_mean=0.4,
        variability_index=0.07,
        trend=VegetationTrend.STABLE,
    )


@pytest.mark.parametrize(
    "ndvi,expected_health",
    [
        (0.70, VegetationHealth.EXCELLENT),
        (0.50, VegetationHealth.GOOD),
        (0.35, VegetationHealth.MODERATE),
        (0.15, VegetationHealth.POOR),
    ],
)
def test_health_classification(ndvi, expected_health):
    metrics = _make(ndvi)
    assert metrics.health == expected_health


def test_values_are_rounded():
    metrics = _make(0.123456789)
    assert metrics.ndvi_mean == round(0.123456789, 4)
