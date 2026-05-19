"""Seed the database with example data for development."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.domain.entities.analysis import Analysis
from src.domain.entities.field import Field
from src.domain.value_objects.requested_metrics import RequestedMetric
from src.infrastructure.database.connection import get_session_factory
from src.infrastructure.database.repositories import SQLAnalysisRepository, SQLFieldRepository

SAMPLE_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [
            [-1.5601, 47.2184],
            [-1.5401, 47.2184],
            [-1.5401, 47.2384],
            [-1.5601, 47.2384],
            [-1.5601, 47.2184],
        ]
    ],
}


async def seed() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        field_repo = SQLFieldRepository(session)
        analysis_repo = SQLAnalysisRepository(session)

        existing = await field_repo.get_by_external_id("field_seed_001")
        if existing:
            print("Seed data already present.")
            return

        field = Field.create(
            external_id="field_seed_001",
            geometry=SAMPLE_GEOMETRY,
            area_ha=23.7,
        )
        field = await field_repo.save(field)
        print(f"Created field: {field.id} (external: {field.external_id})")

        analysis = Analysis.create(
            field_id=field.id,
            requested_metrics=[
                RequestedMetric.NDVI,
                RequestedMetric.NDWI,
                RequestedMetric.CLOUD,
                RequestedMetric.TILES,
                RequestedMetric.ALERTS,
            ],
        )
        analysis = await analysis_repo.save(analysis)
        print(f"Created analysis: {analysis.id}")

        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
