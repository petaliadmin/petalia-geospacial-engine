from typing import Any

import structlog

from src.application.use_cases.create_analysis_use_case import AbstractTaskPublisher
from src.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger(__name__)


class CeleryTaskPublisher(AbstractTaskPublisher):
    """Publishes analysis jobs to the Celery queue."""

    async def publish_analysis_job(
        self,
        analysis_id: str,
        field_id: str,
        external_field_id: str,
        geometry: dict[str, Any],
        requested_metrics: list[str],
    ) -> None:
        celery_app.send_task(
            "src.infrastructure.workers.analysis_worker.run_analysis",
            kwargs={
                "analysis_id": analysis_id,
                "field_id": field_id,
                "external_field_id": external_field_id,
                "geometry": geometry,
                "requested_metrics": requested_metrics,
            },
            task_id=analysis_id,
            queue="analysis",
        )
        logger.info(
            "analysis_job_published",
            analysis_id=analysis_id,
            field_id=field_id,
            external_field_id=external_field_id,
        )
