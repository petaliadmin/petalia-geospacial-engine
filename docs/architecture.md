# Architecture

## Clean Architecture Layers

### Domain Layer (`src/domain/`)
Pure Python business logic. No infrastructure dependencies.

- **Entities**: `Field`, `Analysis`, `SatelliteObservation`, `VegetationMetrics`, `AgronomicAlert`
- **Value Objects**: `AnalysisStatus`, `AlertSeverity`, `AlertType`, `VegetationTrend`, `VegetationHealth`, `Geometry`, `RequestedMetric`
- **Repository Interfaces**: Abstract base classes defining persistence contracts
- **Domain Services**: `AlertDetectionService` (alert rules), `AnalysisDomainService` (lifecycle guards)

### Application Layer (`src/application/`)
Orchestrates domain objects. No direct infrastructure access.

- **Commands**: `CreateAnalysisCommand`
- **Queries**: `GetAnalysisQuery`, `GetFieldLatestQuery`, `GetFieldTimeseriesQuery`, `GetFieldAlertsQuery`
- **Use Cases**: One class per operation, injected via DI
- **DTOs**: Data transfer objects crossing layer boundaries

### Infrastructure Layer (`src/infrastructure/`)
Implements domain interfaces. Owns all external I/O.

- **database/**: SQLAlchemy 2 models, async repositories, Alembic migrations
- **cache/**: Redis client, `RedisCacheService` implementing `AbstractCacheService`
- **messaging/**: Celery app configuration, `CeleryTaskPublisher`
- **earth_engine/**: GEE client initialization, `SentinelImageFetcher`, `IndexCalculator`
- **workers/**: `analysis_worker` Celery task (full 14-step pipeline)
- **monitoring/**: structlog configuration, Prometheus metrics, OpenTelemetry tracing

### Presentation Layer (`src/presentation/`)
HTTP interface. Translates HTTP ↔ application DTOs.

- **api/**: FastAPI routers — analyses, fields, health
- **schemas/**: Pydantic v2 request/response models
- **middlewares/**: JWT+API key auth, request logging with `structlog`

## Sequence Diagram — Create Analysis

```
Client          API              UseCase          Queue          Worker         GEE
  │──POST /v1/analyses──►│                                                      │
  │              │─────────────────►│                                           │
  │              │         ├─validate geometry                                  │
  │              │         ├─upsert Field                                       │
  │              │         ├─create Analysis(PENDING)                           │
  │              │         └─────publish_job──►│                               │
  │◄─202 PENDING─│                             │                               │
  │                                            │─pick up job──►│               │
  │                                                    │─mark RUNNING           │
  │                                                    │─init GEE──────────────►│
  │                                                    │─fetch Sentinel-2───────►│
  │                                                    │◄─image composite────────│
  │                                                    │─compute NDVI/NDWI      │
  │                                                    │─generate tiles─────────►│
  │                                                    │◄─tile/thumbnail URLs────│
  │                                                    │─detect alerts           │
  │                                                    │─persist results         │
  │                                                    │─mark COMPLETED          │
  │                                                    │─invalidate Redis cache  │
  │──GET /v1/analyses/{id}──►│                                                  │
  │◄─200 COMPLETED───────────│                                                  │
```

## CQRS Pattern

```
Commands (write side):               Queries (read side):
CreateAnalysisCommand                GetAnalysisQuery
    │                                    │
    ▼                                    ▼
CreateAnalysisUseCase              GetAnalysisUseCase
    │                                    │
    ├─Field CRUD (PostgreSQL)            ├─Cache lookup (Redis)
    ├─Analysis CREATE (PostgreSQL)       ├─Analysis + Metrics + Alerts (PostgreSQL)
    └─Task publish (Celery/Redis)        └─Tile URLs (Redis)
```
