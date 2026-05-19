from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_export_deps():
    with (
        patch("src.infrastructure.workers.gee_export_worker.get_worker_session_factory") as mock_sf,
        patch("src.infrastructure.workers.gee_export_worker.initialize_earth_engine"),
        patch(
            "src.infrastructure.workers.gee_export_worker.get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("src.infrastructure.earth_engine.image_fetcher.SentinelImageFetcher") as mock_fetcher,
        patch.dict("sys.modules", {"ee": MagicMock()}),
        patch(
            "src.infrastructure.workers.gee_export_worker._poll_and_download_export",
            new_callable=AsyncMock,
        ) as mock_poll,
        patch("src.infrastructure.workers.gee_export_worker._compute_rasterio_stats") as mock_stats,
        patch("src.infrastructure.workers.gee_export_worker.AlertDetectionService"),
        patch(
            "src.infrastructure.workers.gee_export_worker.SQLAnalysisRepository"
        ) as mock_analysis_repo,
        patch(
            "src.infrastructure.workers.gee_export_worker.SQLObservationRepository"
        ) as mock_obs_repo,
        patch(
            "src.infrastructure.workers.gee_export_worker.SQLMetricsRepository"
        ) as mock_metrics_repo,
        patch("src.infrastructure.workers.gee_export_worker.SQLAlertRepository") as mock_alert_repo,
        patch("src.infrastructure.workers.gee_export_worker.asyncio.sleep", new_callable=AsyncMock),
        patch("src.infrastructure.workers.gee_export_worker.os.unlink") as mock_unlink,
    ):
        yield {
            "sf": mock_sf,
            "redis": mock_redis,
            "fetcher": mock_fetcher,
            "poll": mock_poll,
            "stats": mock_stats,
            "analysis_repo": mock_analysis_repo,
            "metrics_repo": mock_metrics_repo,
            "obs_repo": mock_obs_repo,
            "alert_repo": mock_alert_repo,
            "unlink": mock_unlink,
        }


@pytest.mark.asyncio
async def test_gee_export_worker_success(mock_export_deps):
    from src.infrastructure.workers.gee_export_worker import _execute_export_pipeline

    analysis_mock = MagicMock()
    analysis_mock.id = "ana-1"
    analysis_mock.field_id = "field-1"

    mock_export_deps["analysis_repo"].return_value.get_by_id = AsyncMock(return_value=analysis_mock)
    mock_export_deps["analysis_repo"].return_value.update = AsyncMock()

    mock_session = AsyncMock()
    mock_export_deps["sf"].return_value.return_value.__aenter__ = AsyncMock(
        return_value=mock_session
    )
    mock_export_deps["sf"].return_value.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_export_deps["metrics_repo"].return_value.get_timeseries_for_field = AsyncMock(
        return_value=[]
    )
    mock_export_deps["obs_repo"].return_value.save = AsyncMock()
    mock_export_deps["metrics_repo"].return_value.save = AsyncMock()
    mock_export_deps["alert_repo"].return_value.save_many = AsyncMock()

    # Mock image fetcher
    mock_fetch_result = MagicMock()
    from datetime import datetime

    mock_fetch_result.acquisition_date = datetime(2026, 5, 18, tzinfo=UTC)
    mock_fetch_result.cloud_coverage = 0.1
    mock_fetch_result.scene_count = 2
    mock_fetch_result.image = MagicMock()
    mock_fetch_result.image.select.return_value = MagicMock()
    mock_export_deps["fetcher"].return_value.fetch.return_value = mock_fetch_result

    mock_export_deps["poll"].return_value = "/tmp/fake.tif"

    mock_export_deps["stats"].return_value = {
        "ndvi_mean": 0.5,
        "ndvi_min": 0.1,
        "ndvi_max": 0.9,
        "ndvi_std": 0.1,
        "ndmi_mean": 0.2,
        "ndre_mean": 0.3,
        "savi_mean": 0.4,
        "evi2_mean": 0.5,
        "variability_index": 0.1,
    }

    geometry = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}

    res = await _execute_export_pipeline(
        analysis_id="ana-1",
        field_id="field-1",
        external_field_id="ext-1",
        geometry=geometry,
        requested_metrics=["NDVI"],
    )

    assert res["status"] == "COMPLETED"
    assert res["analysis_id"] == "ana-1"
    assert res["mode"] == "gee_export"
    mock_export_deps["unlink"].assert_called_with("/tmp/fake.tif")
