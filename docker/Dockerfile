FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ---- dependencies stage ----
FROM base AS deps
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# ---- runtime stage ----
FROM deps AS runtime
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

RUN addgroup --system petalia && adduser --system --group petalia
USER petalia

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
