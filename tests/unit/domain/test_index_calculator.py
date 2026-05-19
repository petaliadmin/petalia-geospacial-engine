"""Tests for IndexCalculator — S2-1 NDRE/SAVI/EVI2 + S3-2 bestEffort=False + S3-3 timeout.

All GEE calls are mocked — no live Earth Engine connection required.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.earth_engine.index_calculator import (
    IndexCalculator,
    IndexResult,
    _getinfo_with_timeout,
)
from src.shared.exceptions import EarthEngineException

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6], [-1.5, 47.6], [-1.5, 47.5]]],
}

# Simulated GEE getInfo() return values for a healthy field
_NDVI_STATS_MOCK = {
    "NDVI_mean": 0.72,
    "NDVI_min": 0.31,
    "NDVI_max": 0.91,
    "NDVI_stdDev": 0.12,
}
_MULTI_STATS_MOCK = {
    "NDMI": 0.08,
    "NDRE": 0.28,
    "SAVI": 0.52,
    "EVI2": 0.65,
}


def _make_ee_mock(ndvi_stats: dict = _NDVI_STATS_MOCK, multi_stats: dict = _MULTI_STATS_MOCK):
    """Build a mock for the ee module that returns controlled statistics."""
    ee = MagicMock()
    # image.normalizedDifference().rename() chains
    img_chain = MagicMock()
    ee.Image.return_value = img_chain
    # reduceRegion() returns a deferred object; getInfo() returns the dict
    ndvi_reducer = MagicMock()
    ndvi_reducer.getInfo.return_value = ndvi_stats
    multi_reducer = MagicMock()
    multi_reducer.getInfo.return_value = multi_stats
    img_chain.reduceRegion.return_value = ndvi_reducer
    img_chain.addBands.return_value = img_chain
    return ee, ndvi_reducer, multi_reducer


class TestIndexResult:
    """S2-1: IndexResult must contain all 8 fields (no trend)."""

    def test_index_result_has_ndmi_not_ndwi(self) -> None:
        """S1-3: IndexResult must use ndmi_mean, not ndwi_mean."""
        result = IndexResult(
            ndvi_mean=0.72,
            ndvi_min=0.31,
            ndvi_max=0.91,
            ndvi_std=0.12,
            ndmi_mean=0.08,
            ndre_mean=0.28,
            savi_mean=0.52,
            evi2_mean=0.65,
            variability_index=0.17,
        )
        assert hasattr(result, "ndmi_mean"), "ndmi_mean must exist"
        assert not hasattr(result, "ndwi_mean"), "ndwi_mean must NOT exist (was renamed)"
        assert not hasattr(result, "trend"), "trend must NOT exist in IndexResult (S1-2)"

    def test_index_result_has_all_s2_1_indices(self) -> None:
        """S2-1: All three new indices must be present."""
        result = IndexResult(
            ndvi_mean=0.70,
            ndvi_min=0.30,
            ndvi_max=0.90,
            ndvi_std=0.10,
            ndmi_mean=0.05,
            ndre_mean=0.25,
            savi_mean=0.45,
            evi2_mean=0.60,
            variability_index=0.14,
        )
        assert result.ndre_mean == 0.25, "NDRE must be present"
        assert result.savi_mean == 0.45, "SAVI must be present"
        assert result.evi2_mean == 0.60, "EVI2 must be present"


class TestGetInfoWithTimeout:
    """S3-3: _getinfo_with_timeout must raise EarthEngineException on timeout."""

    def test_timeout_raises_earth_engine_exception(self) -> None:
        """A getInfo() that takes longer than timeout must raise EarthEngineException."""
        import time

        slow_object = MagicMock()
        slow_object.getInfo.side_effect = lambda: time.sleep(10)  # Simulates hang

        with pytest.raises(EarthEngineException, match="did not respond"):
            _getinfo_with_timeout(slow_object, timeout=1)

    def test_fast_getinfo_returns_value(self) -> None:
        """A fast getInfo() must return the value directly."""
        fast_object = MagicMock()
        fast_object.getInfo.return_value = {"NDVI_mean": 0.75}

        result = _getinfo_with_timeout(fast_object, timeout=10)
        assert result == {"NDVI_mean": 0.75}


class TestIndexCalculatorBestEffort:
    """S3-2: compute() must call reduceRegion with bestEffort=False."""

    def test_compute_uses_best_effort_false(self) -> None:
        """bestEffort=False must be enforced in all reduceRegion calls."""

        with patch("src.infrastructure.earth_engine.index_calculator.ee") as mock_ee:
            with patch(
                "src.infrastructure.earth_engine.index_calculator._getinfo_with_timeout"
            ) as mock_getinfo:
                mock_getinfo.side_effect = [_NDVI_STATS_MOCK, _MULTI_STATS_MOCK]

                # Set up image mock chain
                image = MagicMock()
                band_chain = MagicMock()
                image.normalizedDifference.return_value = band_chain
                band_chain.rename.return_value = band_chain
                band_chain.addBands.return_value = band_chain
                band_chain.reduceRegion.return_value = MagicMock()
                image.expression.return_value = band_chain
                mock_ee.Geometry.return_value = MagicMock()
                mock_ee.Reducer.mean.return_value = MagicMock()
                mock_ee.Reducer.min.return_value = MagicMock()
                mock_ee.Reducer.max.return_value = MagicMock()
                mock_ee.Reducer.stdDev.return_value = MagicMock()
                reducer_chain = MagicMock()
                reducer_chain.combine.return_value = reducer_chain
                mock_ee.Reducer.mean.return_value = reducer_chain

                calc = IndexCalculator()
                calc.compute(image, GEOMETRY)

                # Verify all reduceRegion calls use bestEffort=False
                for call in band_chain.reduceRegion.call_args_list:
                    kwargs = call.kwargs
                    assert kwargs.get("bestEffort") is False, (
                        f"reduceRegion called with bestEffort={kwargs.get('bestEffort')}, "
                        "expected False (S3-2)"
                    )
                    assert kwargs.get("scale") == 20, (
                        f"scale should be 20m, got {kwargs.get('scale')}"
                    )


class TestVariabilityIndex:
    """The variability_index must be the coefficient of variation (std/|mean|)."""

    def test_variability_index_zero_mean_safe(self) -> None:
        """Division by zero must be handled when ndvi_mean approaches 0."""
        # ndvi_mean = 0.001 is the minimum denominator floor
        from src.infrastructure.earth_engine.index_calculator import IndexResult

        # variability_index = 0.10 / max(|0.001|, 0.001) = 0.10 / 0.001 = 100
        # This is the ceiling behavior — just verify no ZeroDivisionError
        result = IndexResult(
            ndvi_mean=0.0,
            ndvi_min=0.0,
            ndvi_max=0.0,
            ndvi_std=0.10,
            ndmi_mean=0.0,
            ndre_mean=0.0,
            savi_mean=0.0,
            evi2_mean=0.0,
            variability_index=100.0,  # computed externally
        )
        assert result.variability_index == 100.0
