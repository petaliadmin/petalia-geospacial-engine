from unittest.mock import AsyncMock

import pytest

from src.application.commands.create_analysis_command import CreateAnalysisCommand
from src.application.use_cases.create_analysis_use_case import CreateAnalysisUseCase
from src.domain.entities.analysis import Analysis
from src.domain.entities.field import Field
from src.domain.services.analysis_domain_service import AnalysisDomainService
from src.domain.value_objects.analysis_status import AnalysisStatus
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.shared.exceptions import AnalysisAlreadyRunningException, InvalidGeometryException

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [[-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6], [-1.5, 47.6], [-1.5, 47.5]]
    ],
}


@pytest.fixture
def field_repo():
    repo = AsyncMock()
    repo.get_by_external_id.return_value = None
    repo.save.side_effect = lambda f: f
    repo.update.side_effect = lambda f: f
    return repo


@pytest.fixture
def analysis_repo():
    repo = AsyncMock()
    repo.get_running_for_field.return_value = None
    repo.save.side_effect = lambda a: a
    return repo


@pytest.fixture
def task_publisher():
    publisher = AsyncMock()
    publisher.publish_analysis_job = AsyncMock()
    return publisher


@pytest.fixture
def use_case(field_repo, analysis_repo, task_publisher):
    return CreateAnalysisUseCase(
        field_repo=field_repo,
        analysis_repo=analysis_repo,
        domain_service=AnalysisDomainService(),
        task_publisher=task_publisher,
    )


@pytest.mark.asyncio
async def test_creates_new_field_and_analysis(use_case, field_repo, analysis_repo, task_publisher):
    command = CreateAnalysisCommand(
        field_id="field_001",
        geometry=GEOMETRY,
        requested_metrics=[RequestedMetric.NDVI],
    )
    result = await use_case.execute(command)

    assert result.field_id == "field_001"
    assert result.status == AnalysisStatus.PENDING
    field_repo.save.assert_called_once()
    analysis_repo.save.assert_called_once()
    task_publisher.publish_analysis_job.assert_called_once()


@pytest.mark.asyncio
async def test_reuses_existing_field(use_case, field_repo):
    existing_field = Field.create("field_001", GEOMETRY, 10.0)
    field_repo.get_by_external_id.return_value = existing_field
    field_repo.update.side_effect = lambda f: f

    command = CreateAnalysisCommand(
        field_id="field_001",
        geometry=GEOMETRY,
        requested_metrics=[RequestedMetric.NDVI],
    )
    await use_case.execute(command)

    field_repo.save.assert_not_called()
    field_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_raises_when_analysis_already_running(use_case, field_repo, analysis_repo):
    existing_field = Field.create("field_001", GEOMETRY, 10.0)
    field_repo.get_by_external_id.return_value = existing_field
    field_repo.update.side_effect = lambda f: f
    running = Analysis.create("field-uuid", [RequestedMetric.NDVI])
    running.mark_running()
    analysis_repo.get_running_for_field.return_value = running

    command = CreateAnalysisCommand(
        field_id="field_001",
        geometry=GEOMETRY,
        requested_metrics=[RequestedMetric.NDVI],
    )
    with pytest.raises(AnalysisAlreadyRunningException):
        await use_case.execute(command)


@pytest.mark.asyncio
async def test_raises_on_invalid_geometry(use_case):
    command = CreateAnalysisCommand(
        field_id="field_001",
        geometry={"type": "INVALID_TYPE"},
        requested_metrics=[RequestedMetric.NDVI],
    )
    with pytest.raises(InvalidGeometryException):
        await use_case.execute(command)
