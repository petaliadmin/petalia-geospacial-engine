from dataclasses import dataclass
from datetime import datetime
from typing import Any

import ee
import structlog

from src.infrastructure.earth_engine.client import get_ee_client
from src.shared.config import get_settings
from src.shared.exceptions import EarthEngineException
from src.shared.utils import date_range_strings

logger = structlog.get_logger(__name__)


@dataclass
class ImageFetchResult:
    image: Any          # ee.Image composite
    acquisition_date: datetime
    cloud_coverage: float
    scene_count: int
    image_source: str


class SentinelImageFetcher:
    """Fetches and preprocesses Sentinel-2 SR imagery from Google Earth Engine."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def fetch(self, geometry: dict[str, Any]) -> ImageFetchResult:
        get_ee_client()

        start_date, end_date = date_range_strings(self._settings.sentinel_date_range_days)
        ee_geometry = ee.Geometry(geometry)

        try:
            collection = (
                ee.ImageCollection(self._settings.sentinel_dataset)
                .filterBounds(ee_geometry)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", self._settings.sentinel_cloud_max))
                .map(self._apply_scl_mask)
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(
                    "no_sentinel_images",
                    start_date=start_date,
                    end_date=end_date,
                )
                collection = (
                    ee.ImageCollection(self._settings.sentinel_dataset)
                    .filterBounds(ee_geometry)
                    .filterDate(start_date, end_date)
                    .map(self._apply_scl_mask)
                )
                count = collection.size().getInfo()

            composite = collection.median().clip(ee_geometry)

            mean_cloud = (
                collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo() or 0.0
            )
            cloud_fraction = mean_cloud / 100.0

            latest_date_info = (
                collection.sort("system:time_start", False)
                .first()
                .date()
                .format("YYYY-MM-dd")
                .getInfo()
            )
            acquisition_date = datetime.strptime(latest_date_info, "%Y-%m-%d")

            logger.info(
                "sentinel_images_fetched",
                scene_count=count,
                cloud_coverage=round(cloud_fraction, 3),
                acquisition_date=latest_date_info,
            )

            return ImageFetchResult(
                image=composite,
                acquisition_date=acquisition_date,
                cloud_coverage=cloud_fraction,
                scene_count=count,
                image_source=self._settings.sentinel_dataset,
            )

        except EarthEngineException:
            raise
        except Exception as exc:
            logger.error("sentinel_fetch_failed", error=str(exc))
            raise EarthEngineException(f"Image fetch failed: {exc}") from exc

    @staticmethod
    def _apply_scl_mask(image: Any) -> Any:
        """Apply Scene Classification Layer (SCL) mask to remove clouds and shadows."""
        scl = image.select("SCL")
        # SCL classes: 3=cloud shadow, 8=cloud medium prob, 9=cloud high prob, 10=thin cirrus
        cloud_mask = (
            scl.neq(3)
            .And(scl.neq(8))
            .And(scl.neq(9))
            .And(scl.neq(10))
        )
        return image.updateMask(cloud_mask)
