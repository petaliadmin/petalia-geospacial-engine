"""Tests for VegetationMetrics entity — S1-2, S1-3, S2-1.

Verifies the domain entity correctly stores all new fields and
rejects the old (pre-migration) field names.
"""

from src.domain.entities.vegetation_metrics import VegetationMetrics
from src.domain.value_objects.vegetation_health import VegetationHealth
from src.domain.value_objects.vegetation_trend import VegetationTrend


class TestVegetationMetricsFields:
    """S1-3 + S2-1: Entity must have ndmi_mean and the three new indices."""

    def test_entity_has_ndmi_mean_not_ndwi(self) -> None:
        """S1-3: ndmi_mean must exist, ndwi_mean must not."""
        m = VegetationMetrics.create(
            analysis_id="a1",
            ndvi_mean=0.65,
            ndvi_min=0.30,
            ndvi_max=0.90,
            ndvi_std=0.12,
            ndmi_mean=0.08,
            variability_index=0.18,
            trend=VegetationTrend.STABLE,
        )
        assert hasattr(m, "ndmi_mean"), "ndmi_mean field required"
        assert not hasattr(m, "ndwi_mean"), "ndwi_mean must not exist (renamed S1-3)"

    def test_entity_has_ndre_savi_evi2_optional(self) -> None:
        """S2-1: Three new optional indices must exist."""
        m = VegetationMetrics.create(
            analysis_id="a1",
            ndvi_mean=0.65,
            ndvi_min=0.30,
            ndvi_max=0.90,
            ndvi_std=0.12,
            ndmi_mean=0.08,
            variability_index=0.18,
            trend=VegetationTrend.STABLE,
            ndre_mean=0.28,
            savi_mean=0.48,
            evi2_mean=0.61,
        )
        assert m.ndre_mean == 0.28
        assert m.savi_mean == 0.48
        assert m.evi2_mean == 0.61

    def test_entity_new_indices_default_to_none(self) -> None:
        """S2-1: New indices must be None when not provided (backward compat)."""
        m = VegetationMetrics.create(
            analysis_id="a1",
            ndvi_mean=0.65,
            ndvi_min=0.30,
            ndvi_max=0.90,
            ndvi_std=0.12,
            ndmi_mean=0.08,
            variability_index=0.18,
            trend=VegetationTrend.STABLE,
        )
        assert m.ndre_mean is None, "ndre_mean must default to None"
        assert m.savi_mean is None, "savi_mean must default to None"
        assert m.evi2_mean is None, "evi2_mean must default to None"

    def test_entity_trend_set_externally(self) -> None:
        """S1-2: trend must be stored in entity (set by AlertDetectionService)."""
        m = VegetationMetrics.create(
            analysis_id="a1",
            ndvi_mean=0.65,
            ndvi_min=0.30,
            ndvi_max=0.90,
            ndvi_std=0.12,
            ndmi_mean=0.08,
            variability_index=0.18,
            trend=VegetationTrend.UP,
        )
        assert m.trend == VegetationTrend.UP


class TestVegetationMetricsRounding:
    """Values must be rounded to 4 decimal places at creation time."""

    def test_ndmi_is_rounded(self) -> None:
        m = VegetationMetrics.create(
            analysis_id="a1",
            ndvi_mean=0.123456789,
            ndvi_min=0.1,
            ndvi_max=0.9,
            ndvi_std=0.05,
            ndmi_mean=0.123456789,
            variability_index=0.1,
            trend=VegetationTrend.STABLE,
        )
        assert m.ndmi_mean == 0.1235

    def test_ndre_is_rounded_when_provided(self) -> None:
        m = VegetationMetrics.create(
            analysis_id="a1",
            ndvi_mean=0.65,
            ndvi_min=0.30,
            ndvi_max=0.90,
            ndvi_std=0.12,
            ndmi_mean=0.08,
            variability_index=0.18,
            trend=VegetationTrend.STABLE,
            ndre_mean=0.2834567,
        )
        assert m.ndre_mean == 0.2835


class TestVegetationMetricsHealth:
    """The .health property must derive from ndvi_mean via VegetationHealth."""

    def test_health_is_derived_from_ndvi(self) -> None:
        m = VegetationMetrics.create(
            analysis_id="a1",
            ndvi_mean=0.80,
            ndvi_min=0.60,
            ndvi_max=0.95,
            ndvi_std=0.08,
            ndmi_mean=0.10,
            variability_index=0.10,
            trend=VegetationTrend.UP,
        )
        assert m.health == VegetationHealth.from_ndvi(0.80)
