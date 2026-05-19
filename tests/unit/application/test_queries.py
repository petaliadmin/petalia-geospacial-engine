from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.queries.get_analysis_query import GetAnalysisQuery
from src.application.queries.get_field_latest_query import GetFieldLatestQuery
from src.application.queries.get_field_timeseries_query import GetFieldTimeseriesQuery
from src.application.use_cases.get_analysis_use_case import (
    GetAnalysisUseCase,
)
from src.application.use_cases.get_field_latest_use_case import GetFieldLatestUseCase
from src.application.use_cases.get_field_timeseries_use_case import GetFieldTimeseriesUseCase
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.shared.exceptions import AnalysisNotFoundException, FieldNotFoundException


@pytest.fixture
def mock_repos():
    return {
        "analysis": AsyncMock(),
        "field": AsyncMock(),
        "metrics": AsyncMock(),
        "obs": AsyncMock(),
        "alert": AsyncMock(),
        "cache": AsyncMock(),
    }


@pytest.mark.asyncio
async def test_get_analysis_use_case_cached(mock_repos):
    uc = GetAnalysisUseCase(
        mock_repos["analysis"],
        mock_repos["field"],
        mock_repos["metrics"],
        mock_repos["obs"],
        mock_repos["alert"],
        mock_repos["cache"],
    )
    mock_repos["cache"].get_analysis.return_value = {
        "field_id": "f1",
        "analysis_id": "a1",
        "analysis_date": "2026-05-18T00:00:00+00:00",
        "status": "COMPLETED",
        "vegetation": {
            "mean_ndvi": 0.5,
            "min_ndvi": 0.1,
            "max_ndvi": 0.9,
            "std_ndvi": 0.1,
            "trend": "STABLE",
            "health": "GOOD",
        },
        "alerts": [],
    }

    res = await uc.execute(GetAnalysisQuery(analysis_id="a1"))
    assert res.analysis_id == "a1"
    assert res.status == AnalysisStatus.COMPLETED


@pytest.mark.asyncio
async def test_get_analysis_use_case_not_found(mock_repos):
    uc = GetAnalysisUseCase(
        mock_repos["analysis"],
        mock_repos["field"],
        mock_repos["metrics"],
        mock_repos["obs"],
        mock_repos["alert"],
        mock_repos["cache"],
    )
    mock_repos["cache"].get_analysis.return_value = None
    mock_repos["analysis"].get_by_id.return_value = None

    with pytest.raises(AnalysisNotFoundException):
        await uc.execute(GetAnalysisQuery(analysis_id="a1"))


@pytest.mark.asyncio
async def test_get_analysis_use_case_success(mock_repos):
    uc = GetAnalysisUseCase(
        mock_repos["analysis"],
        mock_repos["field"],
        mock_repos["metrics"],
        mock_repos["obs"],
        mock_repos["alert"],
        mock_repos["cache"],
    )
    mock_repos["cache"].get_analysis.return_value = None

    analysis = MagicMock()
    analysis.id = "a1"
    analysis.field_id = "f1"
    analysis.completed_at = datetime.now(UTC)
    analysis.status = AnalysisStatus.COMPLETED
    analysis.is_terminal = True
    mock_repos["analysis"].get_by_id.return_value = analysis

    field = MagicMock()
    field.external_id = "ext1"
    mock_repos["field"].get_by_id.return_value = field

    metrics = MagicMock()
    metrics.ndvi_mean = 0.5
    metrics.ndmi_mean = 0.2
    metrics.trend = "STABLE"
    metrics.health = "GOOD"
    mock_repos["metrics"].get_by_analysis_id.return_value = metrics

    mock_repos["obs"].get_by_analysis_id.return_value = MagicMock(cloud_coverage=0.1)
    mock_repos["alert"].get_by_analysis_id.return_value = []

    res = await uc.execute(GetAnalysisQuery(analysis_id="a1"))

    assert res.analysis_id == "a1"
    assert res.field_id == "ext1"
    assert res.vegetation.mean_ndvi == 0.5
    mock_repos["cache"].set_analysis.assert_called_once()


@pytest.mark.asyncio
async def test_get_field_latest_use_case(mock_repos):
    uc = GetFieldLatestUseCase(
        mock_repos["field"],
        mock_repos["analysis"],
        mock_repos["metrics"],
        mock_repos["obs"],
        mock_repos["alert"],
        mock_repos["cache"],
    )
    mock_repos["cache"].get_latest.return_value = None

    mock_repos["field"].get_by_external_id.return_value = None
    with pytest.raises(FieldNotFoundException):
        await uc.execute(GetFieldLatestQuery(field_id="ext1"))

    field = MagicMock()
    field.id = "f1"
    mock_repos["field"].get_by_external_id.return_value = field

    analysis = MagicMock()
    analysis.id = "a1"
    analysis.completed_at = datetime.now(UTC)
    analysis.status = AnalysisStatus.COMPLETED
    mock_repos["analysis"].get_latest_for_field.return_value = analysis

    mock_repos["metrics"].get_by_analysis_id.return_value = MagicMock(ndvi_mean=0.6, ndmi_mean=0.1)
    mock_repos["obs"].get_by_analysis_id.return_value = MagicMock(cloud_coverage=0.0)
    mock_repos["alert"].get_by_analysis_id.return_value = []

    res = await uc.execute(GetFieldLatestQuery(field_id="ext1"))
    assert res.analysis_id == "a1"
    mock_repos["cache"].set_latest.assert_called_once()


@pytest.mark.asyncio
async def test_get_field_timeseries_use_case(mock_repos):
    uc = GetFieldTimeseriesUseCase(
        field_repo=mock_repos["field"],
        analysis_repo=mock_repos["analysis"],
        metrics_repo=mock_repos["metrics"],
        observation_repo=mock_repos["obs"],
        cache_service=mock_repos["cache"],
    )
    mock_repos["cache"].get_timeseries.return_value = None

    mock_repos["field"].get_by_external_id.return_value = None
    with pytest.raises(FieldNotFoundException):
        await uc.execute(GetFieldTimeseriesQuery(field_id="ext1"))

    field = MagicMock()
    field.id = "f1"
    mock_repos["field"].get_by_external_id.return_value = field

    m1 = MagicMock(
        analysis_id="a1",
        ndvi_mean=0.5,
        ndwi_mean=0.2,
        ndre_mean=0.3,
        ndmi_mean=0.4,
        savi_mean=0.5,
        evi2_mean=0.6,
    )
    m2 = MagicMock(
        analysis_id="a2",
        ndvi_mean=0.6,
        ndwi_mean=0.1,
        ndre_mean=0.3,
        ndmi_mean=0.4,
        savi_mean=0.5,
        evi2_mean=0.6,
    )
    mock_repos["metrics"].get_timeseries_for_field.return_value = [m1, m2]
    mock_repos["analysis"].list_for_field.return_value = [MagicMock(id="a1"), MagicMock(id="a2")]

    res = await uc.execute(GetFieldTimeseriesQuery(field_id="ext1"))
    assert len(res.entries) == 2
    mock_repos["cache"].set_timeseries.assert_called_once()
