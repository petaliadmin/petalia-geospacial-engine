from dataclasses import dataclass
from typing import Any

import ee
import structlog

from src.domain.value_objects.vegetation_trend import VegetationTrend
from src.shared.exceptions import EarthEngineException

logger = structlog.get_logger(__name__)


@dataclass
class IndexResult:
    ndvi_mean: float
    ndvi_min: float
    ndvi_max: float
    ndvi_std: float
    ndwi_mean: float
    variability_index: float
    trend: VegetationTrend


@dataclass
class TileResult:
    tile_url: str
    thumbnail_url: str


class IndexCalculator:
    """Computes NDVI, NDWI and related statistics from a Sentinel-2 composite."""

    NDVI_VIS = {
        "min": -0.2,
        "max": 1.0,
        "palette": ["FF0000", "FFFF00", "00AA00"],  # red → yellow → green
    }

    def compute(self, image: Any, geometry: dict[str, Any]) -> IndexResult:
        """Compute all vegetation and water indices."""
        try:
            ee_geometry = ee.Geometry(geometry)

            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            ndwi = image.normalizedDifference(["B8", "B11"]).rename("NDWI")

            scale = 20
            reducer = ee.Reducer.mean().combine(
                ee.Reducer.min(), sharedInputs=True
            ).combine(
                ee.Reducer.max(), sharedInputs=True
            ).combine(
                ee.Reducer.stdDev(), sharedInputs=True
            )

            ndvi_stats = ndvi.reduceRegion(
                reducer=reducer,
                geometry=ee_geometry,
                scale=scale,
                maxPixels=1e9,
                bestEffort=True,
            ).getInfo()

            ndwi_stats = ndwi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=ee_geometry,
                scale=scale,
                maxPixels=1e9,
                bestEffort=True,
            ).getInfo()

            ndvi_mean = float(ndvi_stats.get("NDVI_mean") or 0.0)
            ndvi_min = float(ndvi_stats.get("NDVI_min") or 0.0)
            ndvi_max = float(ndvi_stats.get("NDVI_max") or 0.0)
            ndvi_std = float(ndvi_stats.get("NDVI_stdDev") or 0.0)
            ndwi_mean = float(ndwi_stats.get("NDWI") or 0.0)

            variability_index = ndvi_std / max(abs(ndvi_mean), 0.001)
            trend = self._compute_trend(ndvi_mean, ndvi_std)

            logger.info(
                "indices_computed",
                ndvi_mean=round(ndvi_mean, 4),
                ndwi_mean=round(ndwi_mean, 4),
                trend=trend,
            )

            return IndexResult(
                ndvi_mean=ndvi_mean,
                ndvi_min=ndvi_min,
                ndvi_max=ndvi_max,
                ndvi_std=ndvi_std,
                ndwi_mean=ndwi_mean,
                variability_index=variability_index,
                trend=trend,
            )

        except EarthEngineException:
            raise
        except Exception as exc:
            logger.error("index_computation_failed", error=str(exc))
            raise EarthEngineException(f"Index computation failed: {exc}") from exc

    def generate_tiles(self, image: Any, geometry: dict[str, Any]) -> TileResult:
        """Generate tile URL and thumbnail PNG URL from NDVI image."""
        try:
            ee_geometry = ee.Geometry(geometry)
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

            map_id = ndvi.getMapId(self.NDVI_VIS)
            tile_url = map_id["tile_fetcher"].url_format

            thumbnail_url = ndvi.getThumbURL({
                **self.NDVI_VIS,
                "region": ee_geometry,
                "dimensions": 512,
                "format": "png",
            })

            logger.info("tiles_generated")
            return TileResult(tile_url=tile_url, thumbnail_url=thumbnail_url)

        except Exception as exc:
            logger.error("tile_generation_failed", error=str(exc))
            raise EarthEngineException(f"Tile generation failed: {exc}") from exc

    @staticmethod
    def _compute_trend(ndvi_mean: float, ndvi_std: float) -> VegetationTrend:
        """Classify vegetation trend based on NDVI stats."""
        if ndvi_mean >= 0.5:
            return VegetationTrend.UP
        if ndvi_mean <= 0.2:
            return VegetationTrend.DOWN
        if ndvi_std > 0.15:
            return VegetationTrend.STABLE
        return VegetationTrend.STABLE
