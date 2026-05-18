# Petalia Geospatial Engine

**Spatial Intelligence as a Service** — autonomous geospatial microservice for Petalia Field Pro.

## Overview

The Petalia Geospatial Engine is a production-grade Python microservice that ingests field geometries, retrieves Sentinel-2 satellite imagery via Google Earth Engine, computes vegetation health indices (NDVI, NDWI), generates tile maps, detects agronomic alerts, and exposes everything through a clean REST API.

```
POST /v1/analyses → async job → EE pipeline → results stored → GET endpoints
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Presentation Layer                  │
│   FastAPI (JWT + API Key + Rate Limiting + CORS)     │
│   POST /analyses  GET /analyses/{id}                 │
│   GET /fields/{id}/latest|timeseries|tiles|alerts    │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                 Application Layer                    │
│  CQRS: Commands → Use Cases → DTOs                  │
│  Queries → Use Cases → DTOs                         │
└──────┬───────────────────────────────────┬──────────┘
       │                                   │
┌──────▼──────────┐              ┌─────────▼──────────┐
│  Domain Layer   │              │Infrastructure Layer │
│  Entities       │              │  PostgreSQL+PostGIS │
│  Value Objects  │              │  Redis Cache        │
│  Repository     │◄─────────────│  Celery Workers     │
│  Interfaces     │              │  Google Earth Engine│
│  Domain Svcs    │              │  Prometheus/OTel    │
└─────────────────┘              └────────────────────┘
```

### Design Decisions

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Task queue | **Celery** over RQ | Production battle-tested, Flower monitoring, complex retry strategies, task chains |
| Cache strategy | **Redis** with per-type TTL | Latest: 24h, timeseries: 7d, tiles: 30d — balances freshness and compute cost |
| Auth | **JWT + API key** dual-mode | JWT for user apps, API key for internal service-to-service |
| Satellite data | **COPERNICUS/S2_SR_HARMONIZED** | Harmonized surface reflectance, cloud-masked via SCL |
| Async DB | **asyncpg + SQLAlchemy 2** | Full async, connection pooling |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Google Earth Engine service account credentials

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 2. Place GEE credentials

```bash
mkdir secrets
cp /path/to/your/gee_service_account.json secrets/gee_service_account.json
```

### 3. Start all services

```bash
docker compose up -d --build
```

### 4. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 5. Access the API

- **Swagger UI**: http://localhost:8000/docs
- **Flower (Celery)**: http://localhost:5555
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001

---

## API Reference

### Authentication

All endpoints require one of:
- **Bearer token**: `Authorization: Bearer <JWT>`
- **API Key**: `X-API-Key: <key>`

### Submit Analysis

```bash
curl -X POST http://localhost:8000/v1/analyses \
  -H "X-API-Key: petalia-internal-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "fieldId": "field_001",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[
        [-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6],
        [-1.5, 47.6], [-1.5, 47.5]
      ]]
    },
    "requestedMetrics": ["NDVI", "NDWI", "CLOUD", "TILES", "ALERTS"]
  }'
```

**Response (202 Accepted):**
```json
{
  "analysisId": "ana_1a2b3c4d5e6f",
  "status": "PENDING",
  "fieldId": "field_001",
  "createdAt": "2026-05-17T10:00:00Z"
}
```

### Get Analysis Results

```bash
curl http://localhost:8000/v1/analyses/ana_1a2b3c4d5e6f \
  -H "X-API-Key: petalia-internal-key-change-me"
```

**Response (200 OK):**
```json
{
  "fieldId": "field_001",
  "analysisId": "ana_1a2b3c4d5e6f",
  "analysisDate": "2026-05-17T10:05:00Z",
  "status": "COMPLETED",
  "vegetation": {
    "meanNdvi": 0.74,
    "minNdvi": 0.42,
    "maxNdvi": 0.91,
    "stdNdvi": 0.08,
    "trend": "UP",
    "health": "EXCELLENT"
  },
  "water": { "meanNdwi": 0.58 },
  "alerts": [],
  "visualization": {
    "tileUrl": "https://earthengine.googleapis.com/.../tiles/{z}/{x}/{y}",
    "thumbnailUrl": "https://earthengine.googleapis.com/.../thumbnail.png"
  },
  "cloudCoverage": 0.12
}
```

### Get Latest Analysis for a Field

```bash
curl http://localhost:8000/v1/fields/field_001/latest \
  -H "X-API-Key: petalia-internal-key-change-me"
```

### Get NDVI Timeseries

```bash
curl "http://localhost:8000/v1/fields/field_001/timeseries?limit=30" \
  -H "X-API-Key: petalia-internal-key-change-me"
```

### Get Tile Map URL

```bash
curl http://localhost:8000/v1/fields/field_001/tiles \
  -H "X-API-Key: petalia-internal-key-change-me"
```

### Get Agronomic Alerts

```bash
curl http://localhost:8000/v1/fields/field_001/alerts \
  -H "X-API-Key: petalia-internal-key-change-me"
```

---

## Analysis Pipeline (14 Steps)

```
Step 1  ← Receive payload (fieldId, geometry, requestedMetrics)
Step 2  ← Create Analysis entity (PENDING)
Step 3  ← Publish Celery job to 'analysis' queue
Step 4  ← Worker picks up job, marks RUNNING
Step 5  ← Authenticate to GEE via service account
Step 6  ← Load COPERNICUS/S2_SR_HARMONIZED collection
Step 7  ← Apply date filter + cloud filter + SCL mask → median composite
Step 8  ← Compute NDVI = (B8 - B4) / (B8 + B4)
Step 9  ← Compute NDWI = (B8 - B11) / (B8 + B11)
Step 10 ← Compute mean, min, max, std dev, trend
Step 11 ← Generate tile URL + thumbnail PNG (palette: red→yellow→green)
Step 12 ← Detect alerts (NDVI < 0.30, drop > 20%, cloud > 30%)
Step 13 ← Persist observation, metrics, alerts to PostgreSQL
Step 14 ← Mark Analysis COMPLETED, invalidate Redis cache
```

---

## Alert Rules

| Alert Type | Trigger | Severity |
|-----------|---------|---------|
| `NDVI_LOW` | NDVI mean < 0.30 | MEDIUM/HIGH/CRITICAL |
| `NDVI_DROP` | NDVI drop > 20% vs. previous | MEDIUM/HIGH/CRITICAL |
| `HIGH_CLOUD_COVER` | Cloud coverage > 30% | LOW/MEDIUM/HIGH |

---

## Cache Strategy

| Data Type | TTL | Key Pattern |
|-----------|-----|------------|
| Latest analysis | 24h | `petalia:latest:{fieldId}` |
| Timeseries | 7 days | `petalia:timeseries:{fieldId}` |
| Tile URLs | 30 days | `petalia:tiles:{fieldId}` |

Cache is automatically invalidated when a new analysis completes.

If a completed analysis was created within the last **48 hours**, the result is returned from cache without triggering a new analysis.

---

## Development

```bash
# Install dev dependencies
make dev-install

# Run linter
make lint

# Run type checker
make type-check

# Run tests
make test

# Run tests with HTML coverage report
make test-cov

# Start local Celery worker
make worker-local

# Start Flower dashboard
make flower-local
```

---

## Project Structure

```
src/
  domain/          # Entities, Value Objects, Repository interfaces, Domain services
  application/     # CQRS: Commands, Queries, Use Cases, DTOs
  infrastructure/  # DB (SQLAlchemy+PostGIS), Redis, Celery, Earth Engine, Monitoring
  presentation/    # FastAPI routes, Pydantic schemas, Auth middleware
  shared/          # Settings, Exceptions, Utils

tests/
  unit/           # Domain entity and use case tests
  integration/    # Database and cache integration tests
  api/            # HTTP endpoint tests
  workers/        # Celery worker pipeline tests

docker/           # Dockerfiles, prometheus.yml
alembic/          # Database migrations
scripts/          # Utilities
```

---

## Observability

- **Logs**: Structured JSON via `structlog`, exported to stdout
- **Metrics**: Prometheus endpoint at `/metrics` (analysis duration, cache hits, EE requests)
- **Traces**: OpenTelemetry, exported via OTLP to any compatible backend (Jaeger, Tempo)
- **Health**: `/health` (liveness) + `/health/ready` (readiness — DB + Redis)
- **Celery**: Flower dashboard at `:5555`

---

## Security

- JWT RS256/HS256 access tokens (configurable)
- API key authentication for service-to-service calls
- CORS allowlist (configurable per environment)
- Rate limiting per IP: 100 req/min default, 10 req/min for analysis creation
- Non-root container user
- GEE credentials via Docker secrets (not environment variables)
