from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_ee_env():
    with (
        patch("src.infrastructure.earth_engine.image_fetcher.get_ee_client") as mock_client,
        patch("src.infrastructure.earth_engine.image_fetcher.get_settings") as mock_settings,
        patch("src.infrastructure.earth_engine.image_fetcher.ee") as mock_ee,
    ):
        yield {"client": mock_client, "settings": mock_settings, "ee": mock_ee}


def test_sentinel_image_fetcher_success(mock_ee_env):
    from src.infrastructure.earth_engine.image_fetcher import SentinelImageFetcher

    mock_settings = mock_ee_env["settings"].return_value
    mock_settings.sentinel_date_range_max_days = 90
    mock_settings.sentinel_dataset = "COPERNICUS/S2_SR_HARMONIZED"
    mock_settings.sentinel_cloud_max = 20
    mock_settings.composite_method = "median"

    fetcher = SentinelImageFetcher()
    geometry = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}

    # Mock ee components
    mock_collection = MagicMock()
    mock_collection.size.return_value.getInfo.return_value = 5
    mock_collection.aggregate_mean.return_value.getInfo.return_value = 10.5

    mock_date = MagicMock()
    mock_date.date.return_value.format.return_value.getInfo.return_value = "2026-05-18"
    mock_collection.sort.return_value.first.return_value = mock_date

    mock_composite = MagicMock()
    mock_collection.median.return_value.clip.return_value = mock_composite

    # Make _build_collection return mock_collection
    fetcher._build_collection = MagicMock(return_value=mock_collection)

    res = fetcher.fetch(geometry)

    assert res.scene_count == 5
    assert res.cloud_coverage == 0.105
    assert res.image_source == "COPERNICUS/S2_SR_HARMONIZED"
    assert res.image == mock_composite


def test_sentinel_image_fetcher_fallback(mock_ee_env):
    from src.infrastructure.earth_engine.image_fetcher import SentinelImageFetcher

    mock_settings = mock_ee_env["settings"].return_value
    mock_settings.sentinel_date_range_max_days = 90
    mock_settings.composite_method = "p80"

    fetcher = SentinelImageFetcher()
    geometry = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}

    def side_effect(*args, **kwargs):
        with_cloud = kwargs.get("with_cloud_filter", args[3] if len(args) > 3 else True)
        if with_cloud:
            # with_cloud_filter=True -> 0 size
            m = MagicMock()
            m.size.return_value.getInfo.return_value = 0
            return m
        else:
            # with_cloud_filter=False -> fallback
            m = MagicMock()
            m.size.return_value.getInfo.return_value = 2
            m.aggregate_mean.return_value.getInfo.return_value = 80.0
            date_mock = m.sort.return_value.first.return_value.date.return_value
            date_mock.format.return_value.getInfo.return_value = "2026-05-10"
            m.reduce.return_value.clip.return_value = MagicMock()
            return m

    fetcher._build_collection = MagicMock(side_effect=side_effect)

    res = fetcher.fetch(geometry)

    assert res.scene_count == 2
    assert res.cloud_coverage == 0.8


def test_sentinel_image_fetcher_no_images(mock_ee_env):
    from src.infrastructure.earth_engine.image_fetcher import SentinelImageFetcher
    from src.shared.exceptions import EarthEngineException

    mock_settings = mock_ee_env["settings"].return_value
    mock_settings.sentinel_date_range_max_days = 90

    fetcher = SentinelImageFetcher()
    geometry = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}

    mock_collection = MagicMock()
    mock_collection.size.return_value.getInfo.return_value = 0
    fetcher._build_collection = MagicMock(return_value=mock_collection)

    with pytest.raises(EarthEngineException) as exc:
        fetcher.fetch(geometry)

    assert "No Sentinel-2 imagery available" in str(exc.value)
