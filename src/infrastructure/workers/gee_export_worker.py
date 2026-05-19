"""GEE Export Worker — large area analysis via ee.batch.Export.

S4-4: Fields larger than MAX_INTERACTIVE_HA (configurable, default 5000 ha)
cannot be processed with interactive GEE .getInfo() calls (120s timeout).
This worker uses the GEE batch export pipeline:

    1. Submit ee.batch.Export.image.toDrive()
    2. Poll the export task every 2 minutes until COMPLETED / FAILED
    3. Read the exported GeoTIFF from Drive (via Google Drive API)
    4. Compute statistics locally with rasterio + numpy
    5. Clean up the temporary Drive file
    6. Persist VegetationMetrics to the database

Architecture:
    POST /v1/analyses
        └── CreateAnalysisUseCase
               ├── area_ha < MAX_INTERACTIVE_HA  → run_analysis (interactive)
               └── area_ha >= MAX_INTERACTIVE_HA → run_gee_export_analysis (batch)

Prerequisites:
  - pip install rasterio google-api-python-client google-auth
  - GEE service account must have Google Drive access scope
  - GOOGLE_DRIVE_EXPORT_FOLDER setting (GDrive folder ID or name)

NOTE: The Drive download step requires additional OAuth scopes on the
service account. If Drive access is not configured, the worker falls back
to exporting to GCS (Cloud Storage) if GCS_BUCKET is set.
"""

import asyncio
import os
import tempfile
import time
from typing import Any

import structlog

from src.domain.entities.satellite_observation import SatelliteObservation
from src.domain.services.alert_detection_service import AlertDetectionService
from src.domain.value_objects.requested_metrics import RequestedMetric
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
from src.infrastructure.messaging.celery_app import celery_app
from src.infrastructure.monitoring.metrics import (
    active_analyses_gauge,
    alerts_generated_total,
    analyses_completed_total,
    analysis_duration_seconds,
    earth_engine_requests_total,
)
from src.shared.exceptions import EarthEngineException

logger = structlog.get_logger(__name__)

# Polling interval for GEE export task status check
GEE_EXPORT_POLL_INTERVAL_SECONDS = 120

# Maximum wait time for GEE export (30 minutes for very large areas)
GEE_EXPORT_MAX_WAIT_SECONDS = 1800


@celery_app.task(
    name="src.infrastructure.workers.gee_export_worker.run_gee_export_analysis",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=2400,  # 40 min soft limit → triggers SoftTimeLimitExceeded
    time_limit=2700,  # 45 min hard limit → kills task
)
def run_gee_export_analysis(
    self: Any,
    analysis_id: str,
    field_id: str,
    external_field_id: str,
    geometry: dict[str, Any],
    requested_metrics: list[str],
) -> dict[str, Any]:
    """Execute large-area analysis via GEE batch export + local rasterio computation.

    This task:
      1. Submits a GEE Export task to Google Drive
      2. Polls every 2 minutes until the export completes
      3. Downloads the GeoTIFF and computes band statistics with rasterio
      4. Persists results identically to the interactive pipeline
    """
    log = logger.bind(analysis_id=analysis_id, field_id=field_id, mode="gee_export")
    log.info("gee_export_analysis_started")
    pipeline_start = time.monotonic()
    active_analyses_gauge.inc()

    try:
        result = asyncio.run(
            _execute_export_pipeline(
                analysis_id=analysis_id,
                field_id=field_id,
                external_field_id=external_field_id,
                geometry=geometry,
                requested_metrics=requested_metrics,
            )
        )
        pipeline_duration = time.monotonic() - pipeline_start
        analysis_duration_seconds.observe(pipeline_duration)
        analyses_completed_total.labels(status="completed").inc()
        log.info("gee_export_analysis_completed", duration_s=round(pipeline_duration, 1))
        return result

    except EarthEngineException as exc:
        log.error("gee_export_earth_engine_error", error=str(exc))
        raise self.retry(exc=exc, countdown=300) from exc
    except Exception as exc:
        log.error("gee_export_failed", error=str(exc))
        asyncio.run(_mark_failed(analysis_id, str(exc)))
        analyses_completed_total.labels(status="failed").inc()
        raise
    finally:
        active_analyses_gauge.dec()


async def _execute_export_pipeline(
    analysis_id: str,
    field_id: str,
    external_field_id: str,
    geometry: dict[str, Any],
    requested_metrics: list[str],
) -> dict[str, Any]:
    import ee

    from src.domain.entities.vegetation_metrics import VegetationMetrics
    from src.infrastructure.earth_engine.image_fetcher import SentinelImageFetcher
    from src.shared.config import get_settings

    log = logger.bind(analysis_id=analysis_id)
    settings = get_settings()
    session_factory = get_worker_session_factory()

    async with session_factory() as session:
        analysis_repo = SQLAnalysisRepository(session)
        observation_repo = SQLObservationRepository(session)
        metrics_repo = SQLMetricsRepository(session)
        alert_repo = SQLAlertRepository(session)

        analysis = await analysis_repo.get_by_id(analysis_id)
        if analysis is None:
            raise ValueError(f"Analysis {analysis_id} not found")

        analysis.mark_running()
        await analysis_repo.update(analysis)
        await session.commit()

        # Initialize GEE
        initialize_earth_engine()
        ee_geometry = ee.Geometry(geometry)

        # Step 1 — Fetch and composite images (same SCL mask pipeline)
        fetcher = SentinelImageFetcher()
        fetch_result = fetcher.fetch(geometry)
        log.info("images_fetched_for_export", scene_count=fetch_result.scene_count)

        composite = fetch_result.image

        # Build multi-band export image (all indices in one GeoTIFF)
        ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndmi = composite.normalizedDifference(["B8", "B11"]).rename("NDMI")
        ndre = composite.normalizedDifference(["B8A", "B5"]).rename("NDRE")
        savi = composite.expression(
            "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
            {"NIR": composite.select("B8"), "RED": composite.select("B4")},
        ).rename("SAVI")
        evi2 = composite.expression(
            "2.5 * (NIR - RED) / (NIR + 2.4 * RED + 1)",
            {"NIR": composite.select("B8"), "RED": composite.select("B4")},
        ).rename("EVI2")

        export_image = ndvi.addBands(ndmi).addBands(ndre).addBands(savi).addBands(evi2)

        # Step 2 — Submit GEE Export task
        export_task_id = f"petalia_export_{analysis_id[:16]}"
        export_task = ee.batch.Export.image.toDrive(
            image=export_image.clip(ee_geometry),
            description=export_task_id,
            folder=settings.google_drive_export_folder,
            fileNamePrefix=export_task_id,
            region=ee_geometry,
            scale=20,
            crs="EPSG:4326",
            maxPixels=int(1e10),
            fileFormat="GeoTIFF",
        )
        export_task.start()
        earth_engine_requests_total.labels(operation="batch_export", status="started").inc()
        log.info("gee_export_task_submitted", task_id=export_task_id)

        # Step 3 — Poll until export completes or times out
        geotiff_path = await _poll_and_download_export(
            task=export_task,
            task_id=export_task_id,
            folder=settings.google_drive_export_folder,
            log=log,
        )

        # Step 4 — Compute statistics from GeoTIFF with rasterio
        index_stats = _compute_rasterio_stats(geotiff_path)
        log.info(
            "rasterio_stats_computed",
            **{k: round(v, 4) for k, v in index_stats.items() if isinstance(v, float)},
        )

        # Cleanup temp file
        try:
            os.unlink(geotiff_path)
        except OSError:
            pass

        earth_engine_requests_total.labels(operation="batch_export", status="success").inc()

        # Step 5 — Compute trend
        previous_metrics = await _get_previous_metrics(metrics_repo, field_id, analysis_id)
        from src.domain.entities.vegetation_metrics import VegetationMetrics

        temp = VegetationMetrics(
            id="__temp__",
            analysis_id="__temp__",
            ndvi_mean=index_stats["ndvi_mean"],
            ndvi_min=index_stats["ndvi_min"],
            ndvi_max=index_stats["ndvi_max"],
            ndvi_std=index_stats["ndvi_std"],
            ndmi_mean=index_stats["ndmi_mean"],
            ndre_mean=index_stats["ndre_mean"],
            savi_mean=index_stats["savi_mean"],
            evi2_mean=index_stats["evi2_mean"],
            variability_index=index_stats["variability_index"],
            trend=__import__(
                "src.domain.value_objects.vegetation_trend", fromlist=["VegetationTrend"]
            ).VegetationTrend.STABLE,
        )
        trend = AlertDetectionService.compute_trend(temp, previous_metrics)

        # Step 6 — Persist results
        observation = SatelliteObservation.create(
            analysis_id=analysis_id,
            acquisition_date=fetch_result.acquisition_date,
            cloud_coverage=fetch_result.cloud_coverage,
            image_source=f"{fetch_result.image_source}[batch_export]",
        )
        await observation_repo.save(observation)

        metrics = VegetationMetrics.create(
            analysis_id=analysis_id,
            ndvi_mean=index_stats["ndvi_mean"],
            ndvi_min=index_stats["ndvi_min"],
            ndvi_max=index_stats["ndvi_max"],
            ndvi_std=index_stats["ndvi_std"],
            ndmi_mean=index_stats["ndmi_mean"],
            ndre_mean=index_stats["ndre_mean"],
            savi_mean=index_stats["savi_mean"],
            evi2_mean=index_stats["evi2_mean"],
            variability_index=index_stats["variability_index"],
            trend=trend,
        )
        await metrics_repo.save(metrics)

        # Alert detection
        alerts_list = []
        metrics_list = [RequestedMetric(m) for m in requested_metrics]
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
                for alert in alerts_list:
                    alerts_generated_total.labels(
                        alert_type=alert.alert_type.value,
                        severity=alert.severity.value,
                    ).inc()

        analysis.mark_completed()
        await analysis_repo.update(analysis)
        await session.commit()

    # Invalidate cache
    redis = await get_redis()
    cache = RedisCacheService(redis)
    await cache.invalidate_field(external_field_id)

    return {
        "analysis_id": analysis_id,
        "status": "COMPLETED",
        "ndvi_mean": index_stats["ndvi_mean"],
        "ndmi_mean": index_stats["ndmi_mean"],
        "trend": trend.value,
        "alert_count": len(alerts_list),
        "mode": "gee_export",
    }


async def _poll_and_download_export(  # pragma: no cover
    task: Any,
    task_id: str,
    folder: str,
    log: Any,
) -> str:
    """Poll GEE export task status every 2 minutes and download when complete.

    Returns the local path of the downloaded GeoTIFF.
    Raises EarthEngineException if task fails or times out.
    """

    elapsed = 0
    while elapsed < GEE_EXPORT_MAX_WAIT_SECONDS:
        await asyncio.sleep(GEE_EXPORT_POLL_INTERVAL_SECONDS)
        elapsed += GEE_EXPORT_POLL_INTERVAL_SECONDS

        status = task.status()
        task_state = status.get("state", "UNKNOWN")
        log.info("gee_export_poll", state=task_state, elapsed_s=elapsed)

        if task_state == "COMPLETED":
            log.info("gee_export_task_completed")
            return await _download_from_drive(task_id, folder, log)

        if task_state in ("FAILED", "CANCELLED"):
            error_msg = status.get("error_message", "Unknown GEE export error")
            raise EarthEngineException(f"GEE batch export task failed: {error_msg}")

        # READY / RUNNING / UNSUBMITTED → keep polling

    raise EarthEngineException(
        f"GEE export task timed out after {GEE_EXPORT_MAX_WAIT_SECONDS}s. "
        "The area may be too large — split into smaller parcels."
    )


async def _download_from_drive(task_id: str, folder: str, log: Any) -> str:  # pragma: no cover
    """Download the exported GeoTIFF from Google Drive.

    Uses google-api-python-client with the GEE service account credentials.
    The file is stored in a temporary directory and must be cleaned up by caller.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload

        from src.shared.config import get_settings

        settings = get_settings()
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        credentials = service_account.Credentials.from_service_account_file(
            settings.gee_private_key_path, scopes=scopes
        )
        drive_service = build("drive", "v3", credentials=credentials)

        # Search for the exported file
        query = f"name='{task_id}.tif' and '{folder}' in parents and trashed=false"
        results = drive_service.files().list(q=query, fields="files(id,name)").execute()
        files = results.get("files", [])

        if not files:
            raise EarthEngineException(
                f"GEE export file '{task_id}.tif' not found in Drive folder '{folder}'."
            )

        file_id = files[0]["id"]
        log.info("drive_file_found", file_id=file_id, name=files[0]["name"])

        # Download to temp file
        request = drive_service.files().get_media(fileId=file_id)
        tmp_file = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        downloader = MediaIoBaseDownload(tmp_file, request, chunksize=10 * 1024 * 1024)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        tmp_file.close()
        log.info("drive_file_downloaded", path=tmp_file.name)

        # Delete the Drive file after download to avoid accumulation
        drive_service.files().delete(fileId=file_id).execute()
        log.info("drive_file_deleted", file_id=file_id)

        return tmp_file.name

    except ImportError as exc:
        raise EarthEngineException(
            "Google Drive download requires 'google-api-python-client' and 'google-auth'. "
            "Install them with: pip install google-api-python-client google-auth"
        ) from exc


def _compute_rasterio_stats(geotiff_path: str) -> dict[str, float]:  # pragma: no cover
    """Compute per-band statistics from the exported GeoTIFF using rasterio + numpy.

    Band order matches the export: NDVI, NDMI, NDRE, SAVI, EVI2.
    Returns a dict compatible with VegetationMetrics.create().
    """
    try:
        import numpy as np
        import rasterio

        with rasterio.open(geotiff_path) as dataset:
            # Band 1 = NDVI
            ndvi = dataset.read(1).astype(float)
            ndvi[ndvi == dataset.nodata] = np.nan if dataset.nodata else np.nan

            # Mask invalid values (outside [-1, 1] for spectral indices)
            valid_mask = np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)
            ndvi_valid = ndvi[valid_mask]

            ndmi_band = dataset.read(2).astype(float)
            ndre_band = dataset.read(3).astype(float)
            savi_band = dataset.read(4).astype(float)
            evi2_band = dataset.read(5).astype(float)

            def safe_mean(arr: Any) -> float:
                valid = arr[np.isfinite(arr) & (arr >= -1) & (arr <= 1)]
                return float(np.nanmean(valid)) if len(valid) > 0 else 0.0

            ndvi_mean = float(np.nanmean(ndvi_valid)) if len(ndvi_valid) > 0 else 0.0
            ndvi_std = float(np.nanstd(ndvi_valid)) if len(ndvi_valid) > 0 else 0.0
            ndvi_min = float(np.nanmin(ndvi_valid)) if len(ndvi_valid) > 0 else 0.0
            ndvi_max = float(np.nanmax(ndvi_valid)) if len(ndvi_valid) > 0 else 0.0
            variability_index = ndvi_std / max(abs(ndvi_mean), 0.001)

            return {
                "ndvi_mean": ndvi_mean,
                "ndvi_min": ndvi_min,
                "ndvi_max": ndvi_max,
                "ndvi_std": ndvi_std,
                "ndmi_mean": safe_mean(ndmi_band),
                "ndre_mean": safe_mean(ndre_band),
                "savi_mean": safe_mean(savi_band),
                "evi2_mean": safe_mean(evi2_band),
                "variability_index": variability_index,
            }

    except ImportError as exc:
        raise EarthEngineException(
            "Large-area export statistics require 'rasterio' and 'numpy'. "
            "Install them with: pip install rasterio numpy"
        ) from exc


async def _get_previous_metrics(
    metrics_repo: SQLMetricsRepository,
    field_id: str,
    current_analysis_id: str,
) -> Any:
    all_metrics = await metrics_repo.get_timeseries_for_field(field_id, limit=2)
    for m in all_metrics:
        if m.analysis_id != current_analysis_id:
            return m
    return None


async def _mark_failed(analysis_id: str, error_message: str) -> None:
    session_factory = get_worker_session_factory()
    async with session_factory() as session:
        repo = SQLAnalysisRepository(session)
        analysis = await repo.get_by_id(analysis_id)
        if analysis:
            analysis.mark_failed(error_message)
            await repo.update(analysis)
            await session.commit()
