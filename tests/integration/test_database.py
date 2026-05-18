import pytest
import pytest_asyncio

from src.domain.entities.analysis import Analysis
from src.domain.entities.field import Field
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.infrastructure.database.repositories import SQLFieldRepository, SQLAnalysisRepository

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [[-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6], [-1.5, 47.6], [-1.5, 47.5]]
    ],
}


@pytest.mark.asyncio
async def test_field_save_and_retrieve(db_session):
    repo = SQLFieldRepository(db_session)
    field = Field.create("ext_field_001", GEOMETRY, 10.5)

    saved = await repo.save(field)
    retrieved = await repo.get_by_id(saved.id)

    assert retrieved is not None
    assert retrieved.external_id == "ext_field_001"
    assert retrieved.area_ha == 10.5


@pytest.mark.asyncio
async def test_field_get_by_external_id(db_session):
    repo = SQLFieldRepository(db_session)
    field = Field.create("ext_field_unique_002", GEOMETRY, 5.0)
    await repo.save(field)

    found = await repo.get_by_external_id("ext_field_unique_002")
    assert found is not None
    assert found.area_ha == 5.0

    not_found = await repo.get_by_external_id("does_not_exist")
    assert not_found is None


@pytest.mark.asyncio
async def test_analysis_save_and_retrieve(db_session):
    field_repo = SQLFieldRepository(db_session)
    analysis_repo = SQLAnalysisRepository(db_session)

    field = Field.create("ext_field_003", GEOMETRY, 8.0)
    saved_field = await field_repo.save(field)

    analysis = Analysis.create(saved_field.id, [RequestedMetric.NDVI, RequestedMetric.ALERTS])
    saved = await analysis_repo.save(analysis)
    retrieved = await analysis_repo.get_by_id(saved.id)

    assert retrieved is not None
    assert retrieved.field_id == saved_field.id
    assert RequestedMetric.NDVI in retrieved.requested_metrics


@pytest.mark.asyncio
async def test_analysis_status_update(db_session):
    field_repo = SQLFieldRepository(db_session)
    analysis_repo = SQLAnalysisRepository(db_session)

    field = Field.create("ext_field_004", GEOMETRY, 6.0)
    saved_field = await field_repo.save(field)

    analysis = Analysis.create(saved_field.id, [RequestedMetric.NDVI])
    await analysis_repo.save(analysis)

    analysis.mark_running()
    await analysis_repo.update(analysis)

    analysis.mark_completed()
    await analysis_repo.update(analysis)

    retrieved = await analysis_repo.get_by_id(analysis.id)
    assert retrieved is not None
    assert retrieved.is_terminal is True
    assert retrieved.completed_at is not None
