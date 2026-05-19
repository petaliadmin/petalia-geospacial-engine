import asyncio
import time
from typing import Any

import structlog
from celery.exceptions import MaxRetriesExceededError

from src.domain.entities.satellite_observation import SatelliteObservation
from src.domain.entities.vegetation_metrics import VegetationMetrics
from src.domain.services.alert_detection_service import AlertDetectionService
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.domain.value_objects.vegetation_trend import VegetationTrend
from src.infrastructure.cache.cache_service import RedisCacheService
from src.infrastructure.cache.redis_client import get_redis
from src.infrastructure.database.connection import get_worker_session_factory
from src.infrastructure.database.repositories import (
    SQLAlertRepository,
    SQLAnalysisRepository,
    SQLMetricsRepository,
    SQLObservationRepository,
)
from src.infrastructure.earth_engine.client import initialize_earth_engine
from src.infrastructure.earth_engine.image_fetcher import SentinelImageFetcher
from src.infrastructure.earth_engine.index_calculator import IndexCalculator
from src.infrastructure.messaging.celery_app import celery_app

# S2-5: Prometheus metrics — all counters and histograms are now actually incremented
from src.infrastructure.monitoring.metrics import (
    active_analyses_gauge,
    alerts_generated_total,
    analyses_completed_total,
    analysis_duration_seconds,
)
from src.shared.exceptions import EarthEngineException

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="src.infrastructure.workers.analysis_worker.run_analysis",
    bind=True,
    max_retries=10,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_analysis(
    self: Any,
    analysis_id: str,
    field_id: str,
    external_field_id: str,
    geometry: dict[str, Any],
    requested_metrics: list[str],
) -> dict[str, Any]:
    """Celery task that executes the full geospatial analysis pipeline."""
    log = logger.bind(analysis_id=analysis_id, field_id=field_id)
    log.info("analysis_task_started")

    try:
        result = asyncio.run(
            _execute_pipeline(
                analysis_id=analysis_id,
                field_id=field_id,
                external_field_id=external_field_id,
                geometry=geometry,
                requested_metrics=requested_metrics,
            )
        )
        log.info("analysis_task_completed", field_id=field_id)
        return result
    except MaxRetriesExceededError as exc:  # pragma: no cover
        log.error("analysis_max_retries_exceeded", error=str(exc))
        asyncio.run(_mark_failed(analysis_id, "Max retries exceeded — GEE unavailable"))
        analyses_completed_total.labels(status="failed").inc()
        raise
    except EarthEngineException as exc:  # pragma: no cover
        log.error("analysis_earth_engine_error", error=str(exc))
        raise self.retry(exc=exc, countdown=120) from exc
    except Exception as exc:  # pragma: no cover
        log.error("analysis_task_failed", error=str(exc))
        asyncio.run(_mark_failed(analysis_id, str(exc)))
        analyses_completed_total.labels(status="failed").inc()
        raise


async def _execute_pipeline(
    analysis_id: str,
    field_id: str,
    external_field_id: str,
    geometry: dict[str, Any],
    requested_metrics: list[str],
) -> dict[str, Any]:
    log = logger.bind(analysis_id=analysis_id)
    session_factory = get_worker_session_factory()

    # S2-5: Track pipeline wall-clock time for Prometheus histogram
    pipeline_start = time.monotonic()
    active_analyses_gauge.inc()

    try:
        async with session_factory() as session:
            analysis_repo = SQLAnalysisRepository(session)
            observation_repo = SQLObservationRepository(session)
            metrics_repo = SQLMetricsRepository(session)
            alert_repo = SQLAlertRepository(session)

            # Mark running
            analysis = await analysis_repo.get_by_id(analysis_id)
            if analysis is None:
                raise ValueError(f"Analysis {analysis_id} not found")

            analysis.mark_running()
            await analysis_repo.update(analysis)
            await session.commit()
            log.info("analysis_marked_running")

            # Connect Earth Engine
            initialize_earth_engine()

            # Fetch Sentinel-2 images (adaptive window + SCL mask)
            fetcher = SentinelImageFetcher()
            fetch_result = fetcher.fetch(geometry)
            log.info(
                "images_fetched",
                scene_count=fetch_result.scene_count,
                cloud_coverage=fetch_result.cloud_coverage,
            )

            # Compute all indices (NDVI, NDMI, NDRE, SAVI, EVI2)
            calculator = IndexCalculator()
            index_result = calculator.compute(fetch_result.image, geometry)

            # S1-2: Get previous metrics BEFORE saving current ones, so we can compute trend
            previous_metrics = await _get_previous_metrics(metrics_repo, field_id, analysis_id)

            # S1-2: Compute real trend using delta between current and previous NDVI
            trend = AlertDetectionService.compute_trend(
                current=_make_temp_metrics(index_result),
                previous=previous_metrics,
            )

            # Generate tiles if requested
            tile_url = None
            thumbnail_url = None
            metrics_list = [RequestedMetric(m) for m in requested_metrics]
            if RequestedMetric.TILES in metrics_list:
                tile_result = calculator.generate_tiles(fetch_result.image, geometry)
                tile_url = tile_result.tile_url
                thumbnail_url = tile_result.thumbnail_url
                log.info("tiles_generated")

            # Save satellite observation
            observation = SatelliteObservation.create(
                analysis_id=analysis_id,
                acquisition_date=fetch_result.acquisition_date,
                cloud_coverage=fetch_result.cloud_coverage,
                image_source=fetch_result.image_source,
            )
            await observation_repo.save(observation)

            # Save vegetation metrics with all new indices + correct trend
            metrics = VegetationMetrics.create(
                analysis_id=analysis_id,
                ndvi_mean=index_result.ndvi_mean,
                ndvi_min=index_result.ndvi_min,
                ndvi_max=index_result.ndvi_max,
                ndvi_std=index_result.ndvi_std,
                ndmi_mean=index_result.ndmi_mean,  # S1-3: was ndwi_mean
                ndre_mean=index_result.ndre_mean,  # S2-1
                savi_mean=index_result.savi_mean,  # S2-1
                evi2_mean=index_result.evi2_mean,  # S2-1
                variability_index=index_result.variability_index,
                trend=trend,  # S1-2: real temporal trend
            )
            await metrics_repo.save(metrics)

            # Alert detection
            alerts_list: list = []
            if RequestedMetric.ALERTS in metrics_list:
                alert_service = AlertDetectionService()
                alerts_list = alert_service.detect(
                    field_id=field_id,
                    analysis_id=analysis_id,
                    current_metrics=metrics,
                    cloud_coverage=fetch_result.cloud_coverage,
                    previous_metrics=previous_metrics,
                )
                if alerts_list:
                    await alert_repo.save_many(alerts_list)
                    log.info("alerts_saved", count=len(alerts_list))

                    # S2-5: Prometheus — track alerts by type and severity
                    for alert in alerts_list:
                        alerts_generated_total.labels(
                            alert_type=alert.alert_type.value,
                            severity=alert.severity.value,
                        ).inc()

            # Mark completed
            analysis.mark_completed()
            await analysis_repo.update(analysis)
            await session.commit()
            log.info("analysis_completed")

        # Update cache
        redis = await get_redis()
        cache = RedisCacheService(redis)
        await cache.invalidate_field(external_field_id)
        if tile_url:
            await cache.set_tiles(external_field_id, tile_url)
        if thumbnail_url:
            await cache.set_thumbnail(external_field_id, thumbnail_url)

        # S2-5: Prometheus — record completed status and pipeline duration
        pipeline_duration = time.monotonic() - pipeline_start
        analysis_duration_seconds.observe(pipeline_duration)
        analyses_completed_total.labels(status="completed").inc()
        log.info("pipeline_duration_recorded", seconds=round(pipeline_duration, 2))

        return {
            "analysis_id": analysis_id,
            "status": "COMPLETED",
            "ndvi_mean": index_result.ndvi_mean,
            "ndmi_mean": index_result.ndmi_mean,
            "ndre_mean": index_result.ndre_mean,
            "trend": trend.value,
            "alert_count": len(alerts_list),
        }

    finally:
        active_analyses_gauge.dec()


def _make_temp_metrics(index_result: Any) -> VegetationMetrics:
    """Build a lightweight VegetationMetrics for trend comparison without DB round-trip."""
    return VegetationMetrics(
        id="__temp__",
        analysis_id="__temp__",
        ndvi_mean=index_result.ndvi_mean,
        ndvi_min=index_result.ndvi_min,
        ndvi_max=index_result.ndvi_max,
        ndvi_std=index_result.ndvi_std,
        ndmi_mean=index_result.ndmi_mean,
        ndre_mean=index_result.ndre_mean,
        savi_mean=index_result.savi_mean,
        evi2_mean=index_result.evi2_mean,
        variability_index=index_result.variability_index,
        trend=VegetationTrend.STABLE,  # placeholder, will be overwritten
    )


async def _get_previous_metrics(
    metrics_repo: SQLMetricsRepository,
    field_id: str,
    current_analysis_id: str,
) -> "VegetationMetrics | None":
    """Fetch the most recent completed metrics for this field (excluding current analysis)."""
    all_metrics = await metrics_repo.get_timeseries_for_field(field_id, limit=2)
    for m in all_metrics:
        if m.analysis_id != current_analysis_id:
            return m
    return None


async def _mark_failed(analysis_id: str, error_message: str) -> None:  # pragma: no cover
    session_factory = get_worker_session_factory()
    async with session_factory() as session:
        repo = SQLAnalysisRepository(session)
        analysis = await repo.get_by_id(analysis_id)
        if analysis:
            analysis.mark_failed(error_message)
            await repo.update(analysis)
            await session.commit()
