from typing import Any

import structlog

from src.application.use_cases.create_analysis_use_case import AbstractTaskPublisher
from src.infrastructure.messaging.celery_app import celery_app
from src.shared.config import get_settings

logger = structlog.get_logger(__name__)


class CeleryTaskPublisher(AbstractTaskPublisher):
    """Routes analysis jobs to the appropriate Celery worker based on field area.

    S4-4: Fields < MAX_INTERACTIVE_HA use the interactive run_analysis worker.
    Fields >= MAX_INTERACTIVE_HA use the GEE batch export pipeline which handles
    large geometries without the 120s interactive API timeout.
    """

    async def publish_analysis_job(
        self,
        analysis_id: str,
        field_id: str,
        external_field_id: str,
        geometry: dict[str, Any],
        requested_metrics: list[str],
        area_ha: float = 0.0,
    ) -> None:
        settings = get_settings()
        max_interactive = settings.max_interactive_ha

        # S4-4: Route to GEE export worker for large areas
        if area_ha >= max_interactive:
            logger.info(
                "routing_to_gee_export",
                analysis_id=analysis_id,
                area_ha=area_ha,
                threshold_ha=max_interactive,
            )
            celery_app.send_task(
                "src.infrastructure.workers.gee_export_worker.run_gee_export_analysis",
                kwargs={
                    "analysis_id": analysis_id,
                    "field_id": field_id,
                    "external_field_id": external_field_id,
                    "geometry": geometry,
                    "requested_metrics": requested_metrics,
                },
                task_id=f"export_{analysis_id}",
                queue="export",
            )
            logger.info(
                "gee_export_job_published",
                analysis_id=analysis_id,
                area_ha=area_ha,
            )
            return

        # Standard interactive pipeline for small/medium fields
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
            area_ha=area_ha,
            mode="interactive",
        )
