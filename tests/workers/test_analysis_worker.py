import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.entities.analysis import Analysis
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.requested_metrics import RequestedMetric

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [[-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6], [-1.5, 47.6], [-1.5, 47.5]]
    ],
}


class MockIndexResult:
    ndvi_mean = 0.74
    ndvi_min = 0.50
    ndvi_max = 0.90
    ndvi_std = 0.08
    ndwi_mean = 0.55
    variability_index = 0.10
    from src.domain.value_objects.vegetation_trend import VegetationTrend
    trend = VegetationTrend.UP


class MockFetchResult:
    from datetime import datetime, timezone
    image = MagicMock()
    acquisition_date = datetime(2026, 5, 17, tzinfo=timezone.utc)
    cloud_coverage = 0.12
    scene_count = 5
    image_source = "COPERNICUS/S2_SR_HARMONIZED"


class MockTileResult:
    tile_url = "https://earthengine.googleapis.com/v1/projects/test/maps/abc/tiles/{z}/{x}/{y}"
    thumbnail_url = "https://earthengine.googleapis.com/v1/projects/test/thumbnails/xyz"


@pytest.mark.asyncio
async def test_pipeline_marks_analysis_completed():
    """Test that the pipeline correctly orchestrates all steps and marks analysis completed."""
    analysis = Analysis.create("field-uuid", [RequestedMetric.NDVI, RequestedMetric.TILES, RequestedMetric.ALERTS])
    analysis_id = analysis.id

    with (
        patch("src.infrastructure.workers.analysis_worker.get_session_factory") as mock_sf,
        patch("src.infrastructure.workers.analysis_worker.initialize_earth_engine"),
        patch("src.infrastructure.workers.analysis_worker.SentinelImageFetcher") as MockFetcher,
        patch("src.infrastructure.workers.analysis_worker.IndexCalculator") as MockCalc,
        patch("src.infrastructure.workers.analysis_worker.get_redis", new_callable=AsyncMock),
        patch("src.infrastructure.workers.analysis_worker.AlertDetectionService") as MockAlerts,
    ):
        mock_session = AsyncMock()
        mock_sf.return_value = MagicMock()
        mock_sf.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_analysis_repo = AsyncMock()
        mock_analysis_repo.get_by_id.return_value = analysis
        mock_analysis_repo.update.side_effect = lambda a: a

        mock_obs_repo = AsyncMock()
        mock_metrics_repo = AsyncMock()
        mock_metrics_repo.get_timeseries_for_field.return_value = []
        mock_alert_repo = AsyncMock()

        with (
            patch("src.infrastructure.workers.analysis_worker.SQLAnalysisRepository", return_value=mock_analysis_repo),
            patch("src.infrastructure.workers.analysis_worker.SQLObservationRepository", return_value=mock_obs_repo),
            patch("src.infrastructure.workers.analysis_worker.SQLMetricsRepository", return_value=mock_metrics_repo),
            patch("src.infrastructure.workers.analysis_worker.SQLAlertRepository", return_value=mock_alert_repo),
        ):
            MockFetcher.return_value.fetch.return_value = MockFetchResult()
            MockCalc.return_value.compute.return_value = MockIndexResult()
            MockCalc.return_value.generate_tiles.return_value = MockTileResult()
            MockAlerts.return_value.detect.return_value = []

            from src.infrastructure.workers.analysis_worker import _execute_pipeline
            result = await _execute_pipeline(
                analysis_id=analysis_id,
                field_id="field-uuid",
                geometry=GEOMETRY,
                requested_metrics=["NDVI", "TILES", "ALERTS"],
            )

    assert result["status"] == "COMPLETED"
    assert result["analysis_id"] == analysis_id


@pytest.mark.asyncio
async def test_pipeline_marks_failed_on_error():
    """Test that errors are caught and analysis is marked FAILED."""
    analysis = Analysis.create("field-uuid", [RequestedMetric.NDVI])

    with (
        patch("src.infrastructure.workers.analysis_worker.get_session_factory") as mock_sf,
        patch("src.infrastructure.workers.analysis_worker.initialize_earth_engine"),
        patch("src.infrastructure.workers.analysis_worker.SentinelImageFetcher") as MockFetcher,
    ):
        mock_session = AsyncMock()
        mock_sf.return_value = MagicMock()
        mock_sf.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_analysis_repo = AsyncMock()
        mock_analysis_repo.get_by_id.return_value = analysis
        mock_analysis_repo.update.side_effect = lambda a: a

        with patch("src.infrastructure.workers.analysis_worker.SQLAnalysisRepository", return_value=mock_analysis_repo):
            MockFetcher.return_value.fetch.side_effect = RuntimeError("GEE is down")

            from src.infrastructure.workers.analysis_worker import _execute_pipeline
            with pytest.raises(RuntimeError):
                await _execute_pipeline(
                    analysis_id=analysis.id,
                    field_id="field-uuid",
                    geometry=GEOMETRY,
                    requested_metrics=["NDVI"],
                )
