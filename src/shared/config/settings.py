from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_name: str = "petalia-geospatial-engine"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = Field(min_length=32)
    api_key_header: str = "X-API-Key"
    api_key_value: str = "petalia-internal-key-change-me"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Database
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl_latest: int = 86400        # 24h
    redis_cache_ttl_timeseries: int = 604800   # 7 days
    redis_cache_ttl_tiles: int = 2592000       # 30 days

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_serializer: str = "json"
    celery_concurrency: int = 4

    # Google Earth Engine
    gee_service_account: str
    gee_private_key_path: str = "/run/secrets/gee_service_account.json"
    gee_project_id: str

    # Analysis Pipeline
    analysis_cache_ttl_hours: int = 48
    ndvi_low_threshold: float = 0.30
    ndvi_drop_threshold: float = 0.20
    cloud_cover_threshold: float = 0.30
    sentinel_dataset: str = "COPERNICUS/S2_SR_HARMONIZED"
    sentinel_cloud_max: int = 30
    sentinel_date_range_days: int = 30

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # CORS
    cors_origins: str = "http://localhost:3000"
    cors_allow_credentials: bool = True

    # Rate Limiting
    rate_limit_default: str = "100/minute"
    rate_limit_analyses: str = "10/minute"

    # Monitoring
    prometheus_enabled: bool = True
    otlp_endpoint: str = "http://localhost:4317"
    log_level: str = "INFO"
    sentry_dsn: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
