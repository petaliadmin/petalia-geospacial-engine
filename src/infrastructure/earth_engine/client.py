import json
import threading

import ee
import structlog

from src.shared.config import get_settings
from src.shared.exceptions import EarthEngineException

logger = structlog.get_logger(__name__)

_initialized = False
_lock = threading.Lock()


def initialize_earth_engine() -> None:
    """Initialize GEE with service account credentials (idempotent, thread-safe)."""
    global _initialized
    with _lock:
        if _initialized:
            return
        settings = get_settings()
        try:
            credentials = ee.ServiceAccountCredentials(
                email=settings.gee_service_account,
                key_file=settings.gee_private_key_path,
            )
            ee.Initialize(credentials=credentials, project=settings.gee_project_id)
            _initialized = True
            logger.info(
                "earth_engine_initialized",
                account=settings.gee_service_account,
                project=settings.gee_project_id,
            )
        except Exception as exc:
            logger.error("earth_engine_init_failed", error=str(exc))
            raise EarthEngineException(f"Initialization failed: {exc}") from exc


def get_ee_client() -> None:
    """Ensure Earth Engine is initialized before any GEE operation."""
    if not _initialized:
        initialize_earth_engine()
