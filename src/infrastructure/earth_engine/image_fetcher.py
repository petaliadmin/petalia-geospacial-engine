from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import ee
import structlog

from src.infrastructure.earth_engine.client import get_ee_client
from src.infrastructure.monitoring.metrics import (
    earth_engine_duration_seconds,
    earth_engine_requests_total,
)
from src.shared.config import get_settings
from src.shared.exceptions import EarthEngineException
from src.shared.utils import date_range_strings

logger = structlog.get_logger(__name__)


@dataclass
class ImageFetchResult:
    image: Any  # ee.Image composite
    acquisition_date: datetime
    cloud_coverage: float
    scene_count: int
    image_source: str


class SentinelImageFetcher:
    """Fetches and preprocesses Sentinel-2 SR imagery from Google Earth Engine.

    Implements an adaptive temporal window strategy (30 → 60 → 90 days) to
    ensure at least one cloud-free scene is found even in cloudy regions.
    Supports multiple composite methods (median, p40, p80, quality_mosaic).
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def fetch(self, geometry: dict[str, Any]) -> ImageFetchResult:
        get_ee_client()
        ee_geometry = ee.Geometry(geometry)

        try:
            with earth_engine_duration_seconds.labels(operation="fetch").time():
                earth_engine_requests_total.labels(operation="fetch", status="started").inc()
                result = self._fetch_with_adaptive_window(ee_geometry, geometry)
                earth_engine_requests_total.labels(operation="fetch", status="success").inc()
                return result

        except EarthEngineException:
            earth_engine_requests_total.labels(operation="fetch", status="error").inc()
            raise
        except Exception as exc:
            earth_engine_requests_total.labels(operation="fetch", status="error").inc()
            logger.error("sentinel_fetch_failed", error=str(exc))
            raise EarthEngineException(f"Image fetch failed: {exc}") from exc

    def _fetch_with_adaptive_window(
        self,
        ee_geometry: Any,
        geometry: dict[str, Any],
    ) -> ImageFetchResult:
        """S3-1: Adaptive temporal window — tries 30 → 60 → 90 days with cloud filter,
        then falls back to 90 days without cloud filter as last resort."""
        max_days = self._settings.sentinel_date_range_max_days
        windows = [d for d in [30, 60, 90] if d <= max_days]
        # Ensure at least one window
        if not windows:
            windows = [max_days]

        collection = None
        count = 0
        used_days = max_days
        start_date = end_date = ""

        for days in windows:
            start_date, end_date = date_range_strings(days)
            collection = self._build_collection(
                ee_geometry, start_date, end_date, with_cloud_filter=True
            )
            count = collection.size().getInfo()
            if count > 0:
                used_days = days
                logger.info(
                    "sentinel_window_used",
                    days=days,
                    count=count,
                    start_date=start_date,
                    end_date=end_date,
                )
                break
        else:
            # Last resort: 90 days without cloud filter
            start_date, end_date = date_range_strings(max_days)
            collection = self._build_collection(
                ee_geometry, start_date, end_date, with_cloud_filter=False
            )
            count = collection.size().getInfo()
            used_days = max_days
            logger.warning(
                "sentinel_fallback_no_cloud_filter",
                days=max_days,
                count=count,
            )
            if count == 0:
                raise EarthEngineException(
                    f"No Sentinel-2 imagery available for this area in the last {max_days} days. "
                    "The zone may be outside the satellite's coverage."
                )

        # S3-6: Configurable composite method
        composite = self._build_composite(collection, ee_geometry)

        mean_cloud = collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo() or 0.0
        cloud_fraction = mean_cloud / 100.0

        latest_date_info = (
            collection.sort("system:time_start", False)
            .first()
            .date()
            .format("YYYY-MM-dd")
            .getInfo()
        )

        # S1-4: Acquisition date must be timezone-aware (Python 3.11+ requires it)
        acquisition_date = datetime.strptime(latest_date_info, "%Y-%m-%d").replace(tzinfo=UTC)

        logger.info(
            "sentinel_images_fetched",
            scene_count=count,
            cloud_coverage=round(cloud_fraction, 3),
            acquisition_date=latest_date_info,
            temporal_window_days=used_days,
            composite_method=self._settings.composite_method,
        )

        return ImageFetchResult(
            image=composite,
            acquisition_date=acquisition_date,
            cloud_coverage=cloud_fraction,
            scene_count=count,
            image_source=self._settings.sentinel_dataset,
        )

    def _build_collection(
        self,
        ee_geometry: Any,
        start_date: str,
        end_date: str,
        with_cloud_filter: bool,
    ) -> Any:
        """Build a filtered Sentinel-2 image collection."""
        col = (
            ee.ImageCollection(self._settings.sentinel_dataset)
            .filterBounds(ee_geometry)
            .filterDate(start_date, end_date)
            .map(self._apply_scl_mask)
        )
        if with_cloud_filter:
            col = col.filter(
                ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", self._settings.sentinel_cloud_max)
            )
        return col

    def _build_composite(self, collection: Any, ee_geometry: Any) -> Any:
        """S3-6: Build composite image using the configured method."""
        method = self._settings.composite_method

        if method == "p40":
            return collection.reduce(ee.Reducer.percentile([40])).clip(ee_geometry)
        if method == "p80":
            return collection.reduce(ee.Reducer.percentile([80])).clip(ee_geometry)
        if method == "quality_mosaic":
            # Quality mosaic: prioritises pixels with highest NDVI (least cloudy vegetation)
            def add_ndvi(img: Any) -> Any:
                return img.addBands(img.normalizedDifference(["B8", "B4"]).rename("NDVI"))

            return collection.map(add_ndvi).qualityMosaic("NDVI").clip(ee_geometry)

        # Default: median — most stable for small collections
        return collection.median().clip(ee_geometry)

    # ------------------------------------------------------------------
    # S4-2 · Cloud Score+ hybrid mask (complement to SCL)
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_cloud_score_plus_mask(image: Any) -> Any:
        """Hybrid mask: SCL + Cloud Score+ (Google 2023) for maximum quality.

        Cloud Score+ is superior to SCL for thin cirrus and cloud-edge pixels.
        A cs score > 0.6 means the pixel is clear (0 = cloudy, 1 = clear).
        """
        cs_col = (
            ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
            .filterBounds(image.geometry())
            .filterDate(
                ee.Date(image.date().format()),
                ee.Date(image.date().advance(1, "day")),
            )
        )
        cs_img = cs_col.first()
        # Guard: if no Cloud Score+ image available, return image unchanged
        cloud_score_mask = ee.Algorithms.If(
            cs_col.size().gt(0),
            cs_img.select("cs").gte(0.6),
            ee.Image(1),  # all pixels valid if no cs image
        )
        return image.updateMask(ee.Image(cloud_score_mask))

    @staticmethod
    def _apply_scl_mask(image: Any) -> Any:
        """S1-1: Apply Scene Classification Layer (SCL) mask.

        Conservative agricultural mask — excludes all invalid/cloud pixels:
          Class 0  — No Data (missing pixels, must be excluded)
          Class 1  — Saturated / Defective (radiometrically invalid)
          Class 3  — Cloud Shadow
          Class 8  — Cloud Medium Probability
          Class 9  — Cloud High Probability
          Class 10 — Thin Cirrus

        Classes 2 (Dark Area), 4 (Vegetation), 5 (Not Vegetated),
        6 (Water), 7 (Unclassified), 11 (Snow/Ice) are kept.
        """
        scl = image.select("SCL")
        cloud_mask = (
            scl.neq(0)  # No Data
            .And(scl.neq(1))  # Saturated / Defective
            .And(scl.neq(3))  # Cloud Shadow
            .And(scl.neq(8))  # Cloud Medium Probability
            .And(scl.neq(9))  # Cloud High Probability
            .And(scl.neq(10))  # Thin Cirrus
        )
        return image.updateMask(cloud_mask)
