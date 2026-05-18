from prometheus_client import Counter, Gauge, Histogram

# Analysis pipeline metrics
analyses_created_total = Counter(
    "petalia_analyses_created_total",
    "Total number of analyses created",
    ["field_id"],
)

analyses_completed_total = Counter(
    "petalia_analyses_completed_total",
    "Total number of analyses completed",
    ["status"],
)

analysis_duration_seconds = Histogram(
    "petalia_analysis_duration_seconds",
    "Analysis pipeline duration in seconds",
    buckets=[10, 30, 60, 120, 300, 600, 1800],
)

earth_engine_requests_total = Counter(
    "petalia_earth_engine_requests_total",
    "Total Earth Engine API requests",
    ["operation", "status"],
)

earth_engine_duration_seconds = Histogram(
    "petalia_earth_engine_duration_seconds",
    "Earth Engine request duration",
    ["operation"],
    buckets=[1, 5, 10, 30, 60, 120],
)

cache_hits_total = Counter(
    "petalia_cache_hits_total",
    "Total cache hits",
    ["cache_type"],
)

cache_misses_total = Counter(
    "petalia_cache_misses_total",
    "Total cache misses",
    ["cache_type"],
)

alerts_generated_total = Counter(
    "petalia_alerts_generated_total",
    "Total agronomic alerts generated",
    ["alert_type", "severity"],
)

active_analyses_gauge = Gauge(
    "petalia_active_analyses",
    "Number of currently running analyses",
)
