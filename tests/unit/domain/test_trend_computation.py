"""Tests for vegetation trend computation — S1-2.

Verifies that trend is computed from the NDVI delta between two real
observations, not from a single image's statistics.
"""
import pytest

from src.domain.services.alert_detection_service import AlertDetectionService
from src.domain.value_objects.vegetation_trend import VegetationTrend
from tests.conftest import make_metrics


class TestTrendComputation:
    """S1-2: Trend must be derived from temporal NDVI delta, not point classification."""

    def test_trend_none_when_no_previous(self) -> None:
        """Without previous metrics, trend must be STABLE (insufficient data)."""
        current = make_metrics(ndvi_mean=0.70)
        trend = AlertDetectionService.compute_trend(current=current, previous=None)
        assert trend == VegetationTrend.STABLE

    def test_trend_up_when_ndvi_increases_significantly(self) -> None:
        """Delta > +0.05 must be classified as UP."""
        previous = make_metrics(ndvi_mean=0.50)
        current = make_metrics(ndvi_mean=0.60)  # delta = +0.10
        trend = AlertDetectionService.compute_trend(current=current, previous=previous)
        assert trend == VegetationTrend.UP

    def test_trend_down_when_ndvi_drops_significantly(self) -> None:
        """Delta < -0.05 must be classified as DOWN."""
        previous = make_metrics(ndvi_mean=0.75)
        current = make_metrics(ndvi_mean=0.60)  # delta = -0.15
        trend = AlertDetectionService.compute_trend(current=current, previous=previous)
        assert trend == VegetationTrend.DOWN

    def test_trend_stable_within_noise_margin(self) -> None:
        """Delta within ±0.05 must be STABLE (sensor noise tolerance)."""
        previous = make_metrics(ndvi_mean=0.65)
        current = make_metrics(ndvi_mean=0.67)  # delta = +0.02
        trend = AlertDetectionService.compute_trend(current=current, previous=previous)
        assert trend == VegetationTrend.STABLE

    def test_trend_stable_at_exact_boundary(self) -> None:
        """Delta exactly ±0.05 is on the boundary — must be STABLE (strict inequalities)."""
        previous = make_metrics(ndvi_mean=0.65)
        current = make_metrics(ndvi_mean=0.70)  # delta = +0.05 exactly
        trend = AlertDetectionService.compute_trend(current=current, previous=previous)
        assert trend == VegetationTrend.STABLE

    def test_trend_independent_of_absolute_ndvi_level(self) -> None:
        """A low absolute NDVI but increasing trend must still be UP.

        This was the critical bug before S1-2: NDVI=0.25 was classified as DOWN
        regardless of temporal evolution.
        """
        previous = make_metrics(ndvi_mean=0.10)
        current = make_metrics(ndvi_mean=0.20)  # delta = +0.10 — recovering field
        trend = AlertDetectionService.compute_trend(current=current, previous=previous)
        assert trend == VegetationTrend.UP
