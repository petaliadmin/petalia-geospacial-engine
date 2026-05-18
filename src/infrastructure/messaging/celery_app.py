from celery import Celery

from src.shared.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "petalia-geospatial-engine",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=[
            "src.infrastructure.workers.analysis_worker",
            "src.infrastructure.workers.batch_analysis_worker",  # S4-1
            "src.infrastructure.workers.gee_export_worker",      # S4-4
        ],
    )
    app.conf.update(
        task_serializer=settings.celery_task_serializer,
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_reject_on_worker_lost=True,
        task_routes={
            "src.infrastructure.workers.analysis_worker.run_analysis": {"queue": "analysis"},
            "src.infrastructure.workers.batch_analysis_worker.run_analysis_safe": {"queue": "analysis"},
            "src.infrastructure.workers.batch_analysis_worker.on_batch_completed": {"queue": "analysis"},
            "src.infrastructure.workers.gee_export_worker.run_gee_export_analysis": {"queue": "export"},
        },
        task_default_queue="analysis",
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = create_celery_app()
