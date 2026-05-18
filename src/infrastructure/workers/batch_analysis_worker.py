"""Batch analysis worker — Celery group() + chord() native orchestration.

S4-1: Groups multiple run_analysis tasks in a single Celery primitive,
allowing them to execute in parallel across multiple workers and collecting
results via a chord callback when ALL tasks are complete.

Architecture:
    POST /v1/analyses/batch
        └── batch_analysis_use_case.execute()
               └── publishes Celery group([run_analysis.si(...), ...])
                   |> chord callback: on_batch_completed()
                   └── stores batch result in Redis under batch_id

Why group() over asyncio.gather():
  - asyncio.gather() runs inside the FastAPI worker process — no Celery distribution.
  - group() distributes tasks across ALL available Celery workers in the pool.
  - chord() fires a callback once every task in the group has finished.
  - group() respects retry policies, dead letter queues, and acks_late.
"""
import json
from typing import Any

import structlog
from celery import chord, group, states
from celery.result import AsyncResult

from src.infrastructure.cache.redis_client import get_redis_sync
from src.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger(__name__)

BATCH_RESULT_PREFIX = "petalia:batch:"
BATCH_TTL_SECONDS = 86400  # 24h


# ---------------------------------------------------------------------------
# Chord callback — fires once ALL run_analysis tasks in the group complete
# ---------------------------------------------------------------------------

@celery_app.task(
    name="src.infrastructure.workers.batch_analysis_worker.on_batch_completed",
    bind=True,
    ignore_result=False,
)
def on_batch_completed(self: Any, results: list[dict], batch_id: str) -> dict:
    """Chord callback: aggregates individual task results and stores in Redis.

    `results` is the list of return values from each run_analysis() call,
    in the same order as the group was created.
    Celery automatically injects this as the first positional argument.
    """
    log = logger.bind(batch_id=batch_id, task_count=len(results))

    succeeded = [r for r in results if r.get("status") == "COMPLETED"]
    failed = [r for r in results if r.get("status") != "COMPLETED"]

    summary = {
        "batch_id": batch_id,
        "submitted": len(results),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "results": results,
    }

    # Persist to Redis so the polling endpoint can retrieve it
    redis = get_redis_sync()
    redis.setex(
        f"{BATCH_RESULT_PREFIX}{batch_id}",
        BATCH_TTL_SECONDS,
        json.dumps(summary),
    )
    log.info("batch_completed", succeeded=len(succeeded), failed=len(failed))
    return summary


@celery_app.task(
    name="src.infrastructure.workers.batch_analysis_worker.run_analysis_safe",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_analysis_safe(
    self: Any,
    analysis_id: str,
    field_id: str,
    external_field_id: str,
    geometry: dict[str, Any],
    requested_metrics: list[str],
    batch_id: str,
) -> dict[str, Any]:
    """Wrapper around run_analysis for batch mode.

    Returns a structured result dict even on failure so the chord callback
    can distinguish failed items without raising (which would abort the chord).
    """
    from src.infrastructure.workers.analysis_worker import run_analysis

    log = logger.bind(analysis_id=analysis_id, batch_id=batch_id)
    try:
        result = run_analysis(
            analysis_id=analysis_id,
            field_id=field_id,
            external_field_id=external_field_id,
            geometry=geometry,
            requested_metrics=requested_metrics,
        )
        return result
    except Exception as exc:
        log.error("batch_item_failed", error=str(exc))
        # Return failure dict instead of raising — keeps the chord alive
        return {
            "analysis_id": analysis_id,
            "status": "FAILED",
            "error": str(exc),
        }


def publish_batch_group(
    batch_id: str,
    items: list[dict[str, Any]],
) -> str:
    """Build and dispatch a Celery group() + chord() for a batch of analyses.

    Args:
        batch_id: Unique identifier for this batch (used as Redis key).
        items: List of dicts, each with keys:
               analysis_id, field_id, external_field_id, geometry, requested_metrics.

    Returns:
        batch_id (for polling via /v1/analyses/batch/{batch_id}/status).
    """
    tasks = group(
        run_analysis_safe.s(
            analysis_id=item["analysis_id"],
            field_id=item["field_id"],
            external_field_id=item["external_field_id"],
            geometry=item["geometry"],
            requested_metrics=item["requested_metrics"],
            batch_id=batch_id,
        )
        for item in items
    )

    # chord(group | callback) fires on_batch_completed when all tasks finish
    batch_chord = chord(tasks)(
        on_batch_completed.s(batch_id=batch_id)
    )

    logger.info(
        "batch_group_published",
        batch_id=batch_id,
        item_count=len(items),
        chord_id=batch_chord.id if hasattr(batch_chord, "id") else "unknown",
    )
    return batch_id


def get_batch_result(batch_id: str) -> dict | None:
    """Retrieve batch result from Redis. Returns None if not ready yet."""
    redis = get_redis_sync()
    raw = redis.get(f"{BATCH_RESULT_PREFIX}{batch_id}")
    if raw is None:
        return None
    return json.loads(raw)
