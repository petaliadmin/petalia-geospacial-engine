import concurrent.futures
from dataclasses import dataclass
from typing import Any

import ee
import structlog

from src.infrastructure.monitoring.metrics import (
    earth_engine_duration_seconds,
    earth_engine_requests_total,
)
from src.shared.exceptions import EarthEngineException

logger = structlog.get_logger(__name__)

# S3-3: Maximum seconds to wait for a GEE .getInfo() call before raising
GEE_TIMEOUT_SECONDS = 120


@dataclass
class IndexResult:
    """Result of the full vegetation index computation pipeline.

    S1-2: `trend` field removed — trend requires two observations and is now
          computed by AlertDetectionService after comparing with previous metrics.
    S1-3: `ndwi_mean` renamed to `ndmi_mean` — (B8-B11)/(B8+B11) is the NDMI
          (Gao 1996, leaf water content / moisture stress), NOT the NDWI
          (McFeeters 1996, open water detection). Using the correct name avoids
          misleading agronomists.
    S2-1: NDRE, SAVI, EVI2 added for precision agriculture.
    """

    ndvi_mean: float
    ndvi_min: float
    ndvi_max: float
    ndvi_std: float
    ndmi_mean: float  # S1-3: was ndwi_mean
    ndre_mean: float  # S2-1: Red-Edge — nitrogen/chlorophyll stress
    savi_mean: float  # S2-1: Soil-Adjusted — bare soil correction
    evi2_mean: float  # S2-1: Enhanced — dense canopy saturation correction
    variability_index: float


@dataclass
class TileResult:
    tile_url: str
    thumbnail_url: str


def _getinfo_with_timeout(ee_object: Any, timeout: int = GEE_TIMEOUT_SECONDS) -> Any:
    """S3-3: Wraps .getInfo() with a wall-clock timeout to prevent Celery task hangs.

    GEE can block indefinitely when the service is overloaded. Without a timeout
    the Celery worker is permanently blocked. A 120-second ceiling matches the
    GEE interactive computation quota.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(ee_object.getInfo)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise EarthEngineException(
                f"GEE did not respond within {timeout}s. "
                "The computation may be too large for interactive mode — "
                "consider splitting the geometry or using ee.batch.Export."
            )


class IndexCalculator:
    """Computes NDVI, NDMI, NDRE, SAVI, EVI2 and related statistics from a Sentinel-2 composite.

    All spectral indices are computed in a single reduceRegion call (one GEE round-trip)
    which reduces latency and API quota usage.

    S3-2: scale=20 and bestEffort=False are enforced. bestEffort=True silently degrades
    resolution up to 500 m on large parcels, making statistics meaningless for field-level
    agronomy. scale=20 matches the SWIR bands (B11, B12) used in NDMI.
    """

    # NDVI palette: red → yellow → green (standard agronomic convention)
    NDVI_VIS = {
        "min": -0.2,
        "max": 1.0,
        "palette": ["FF0000", "FFFF00", "00AA00"],
    }

    # S3-2: Fixed scale for all reduceRegion calls — matches SWIR/RedEdge resolution
    _ANALYSIS_SCALE = 20
    _MAX_PIXELS = 1e9

    def compute(self, image: Any, geometry: dict[str, Any]) -> IndexResult:
        """Compute all vegetation indices in a single GEE round-trip.

        Uses a combined multi-band reduceRegion to minimise latency and quota usage.
        """
        try:
            ee_geometry = ee.Geometry(geometry)  # type: ignore[attr-defined]

            # --- S1-3: NDMI (not NDWI) ---
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            ndmi = image.normalizedDifference(["B8", "B11"]).rename("NDMI")  # S1-3

            # --- S2-1: NDRE — Red-Edge chlorophyll index (20m bands B8A, B5) ---
            # Detects nitrogen/chlorophyll stress 2-3 weeks before NDVI reacts
            ndre = image.normalizedDifference(["B8A", "B5"]).rename("NDRE")

            # --- S2-1: SAVI — Soil-Adjusted Vegetation Index ---
            # L=0.5 is the standard soil adjustment factor for semi-arid conditions
            savi = image.expression(
                "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
                {"NIR": image.select("B8"), "RED": image.select("B4")},
            ).rename("SAVI")

            # --- S2-1: EVI2 — Enhanced Vegetation Index (2-band, no Blue needed) ---
            # More robust than NDVI for dense canopy (corn, sunflower) — avoids saturation
            evi2 = image.expression(
                "2.5 * (NIR - RED) / (NIR + 2.4 * RED + 1)",
                {"NIR": image.select("B8"), "RED": image.select("B4")},
            ).rename("EVI2")

            # --- Single combined reduceRegion call for NDVI stats (mean+min+max+std) ---
            ndvi_reducer = (
                ee.Reducer.mean()  # type: ignore[attr-defined]
                .combine(ee.Reducer.min(), sharedInputs=True)  # type: ignore[attr-defined]
                .combine(ee.Reducer.max(), sharedInputs=True)  # type: ignore[attr-defined]
                .combine(ee.Reducer.stdDev(), sharedInputs=True)  # type: ignore[attr-defined]
            )

            # S3-2: bestEffort=False — enforce exact scale, never degrade resolution
            ndvi_stats_raw = ndvi.reduceRegion(
                reducer=ndvi_reducer,
                geometry=ee_geometry,
                scale=self._ANALYSIS_SCALE,
                maxPixels=self._MAX_PIXELS,
                bestEffort=False,  # S3-2
            )

            # Combined pass for NDMI, NDRE, SAVI, EVI2 — one GEE call
            multi_band_image = ndmi.addBands(ndre).addBands(savi).addBands(evi2)
            multi_stats_raw = multi_band_image.reduceRegion(
                reducer=ee.Reducer.mean(),  # type: ignore[attr-defined]
                geometry=ee_geometry,
                scale=self._ANALYSIS_SCALE,
                maxPixels=self._MAX_PIXELS,
                bestEffort=False,  # S3-2
            )

            # S3-3: Apply timeout to all .getInfo() calls
            with earth_engine_duration_seconds.labels(operation="reduce_region").time():
                earth_engine_requests_total.labels(
                    operation="reduce_region", status="started"
                ).inc()
                ndvi_stats = _getinfo_with_timeout(ndvi_stats_raw)
                multi_stats = _getinfo_with_timeout(multi_stats_raw)
                earth_engine_requests_total.labels(
                    operation="reduce_region", status="success"
                ).inc()

            ndvi_mean = float(ndvi_stats.get("NDVI_mean") or 0.0)
            ndvi_min = float(ndvi_stats.get("NDVI_min") or 0.0)
            ndvi_max = float(ndvi_stats.get("NDVI_max") or 0.0)
            ndvi_std = float(ndvi_stats.get("NDVI_stdDev") or 0.0)
            ndmi_mean = float(multi_stats.get("NDMI") or 0.0)
            ndre_mean = float(multi_stats.get("NDRE") or 0.0)
            savi_mean = float(multi_stats.get("SAVI") or 0.0)
            evi2_mean = float(multi_stats.get("EVI2") or 0.0)

            # Coefficient of variation — high value = intra-field heterogeneity
            variability_index = ndvi_std / max(abs(ndvi_mean), 0.001)

            logger.info(
                "indices_computed",
                ndvi_mean=round(ndvi_mean, 4),
                ndmi_mean=round(ndmi_mean, 4),
                ndre_mean=round(ndre_mean, 4),
                savi_mean=round(savi_mean, 4),
                evi2_mean=round(evi2_mean, 4),
                variability_index=round(variability_index, 4),
            )

            return IndexResult(
                ndvi_mean=ndvi_mean,
                ndvi_min=ndvi_min,
                ndvi_max=ndvi_max,
                ndvi_std=ndvi_std,
                ndmi_mean=ndmi_mean,
                ndre_mean=ndre_mean,
                savi_mean=savi_mean,
                evi2_mean=evi2_mean,
                variability_index=variability_index,
            )

        except EarthEngineException:
            earth_engine_requests_total.labels(operation="reduce_region", status="error").inc()
            raise
        except Exception as exc:
            earth_engine_requests_total.labels(operation="reduce_region", status="error").inc()
            logger.error("index_computation_failed", error=str(exc))
            raise EarthEngineException(f"Index computation failed: {exc}") from exc

    def generate_tiles(self, image: Any, geometry: dict[str, Any]) -> TileResult:
        """Generate tile URL and thumbnail PNG URL from NDVI image."""
        try:
            ee_geometry = ee.Geometry(geometry)  # type: ignore[attr-defined]
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

            with earth_engine_duration_seconds.labels(operation="get_map_id").time():
                map_id = ndvi.getMapId(self.NDVI_VIS)
                tile_url = map_id["tile_fetcher"].url_format

                thumbnail_url = ndvi.getThumbURL(
                    {
                        **self.NDVI_VIS,
                        "region": ee_geometry,
                        "dimensions": 512,
                        "format": "png",
                    }
                )

            logger.info("tiles_generated")
            return TileResult(tile_url=tile_url, thumbnail_url=thumbnail_url)

        except Exception as exc:
            logger.error("tile_generation_failed", error=str(exc))
            raise EarthEngineException(f"Tile generation failed: {exc}") from exc
