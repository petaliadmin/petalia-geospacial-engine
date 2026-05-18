.PHONY: help install dev-install lint type-check test test-cov up down logs migrate seed clean

PYTHON := python
PIP := pip
DOCKER_COMPOSE := docker compose

help:
	@echo "Petalia Geospatial Engine — Available commands:"
	@echo ""
	@echo "  install        Install production dependencies"
	@echo "  dev-install    Install dev dependencies"
	@echo "  lint           Run ruff linter"
	@echo "  type-check     Run mypy"
	@echo "  test           Run test suite"
	@echo "  test-cov       Run tests with coverage report"
	@echo "  up             Start all services via docker compose"
	@echo "  down           Stop all services"
	@echo "  logs           Follow logs"
	@echo "  migrate        Run Alembic migrations"
	@echo "  seed           Seed database with example data"
	@echo "  clean          Remove docker volumes"

install:
	$(PIP) install .

dev-install:
	$(PIP) install ".[dev]"

lint:
	ruff check src/ tests/

type-check:
	mypy src/

format:
	ruff format src/ tests/

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-api:
	pytest tests/api/ -v

up:
	$(DOCKER_COMPOSE) up -d --build

up-dev:
	$(DOCKER_COMPOSE) up --build

down:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f api worker

migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(name)"

seed:
	$(PYTHON) scripts/seed_data.py

shell:
	$(PYTHON) -c "from src.main import app; import IPython; IPython.embed()"

clean:
	$(DOCKER_COMPOSE) down -v --remove-orphans

worker-local:
	celery -A src.infrastructure.messaging.celery_app worker \
		--loglevel=info --concurrency=2 --queues=analysis

flower-local:
	celery -A src.infrastructure.messaging.celery_app flower --port=5555

secrets-dir:
	mkdir -p secrets
	@echo "Place your GEE service account JSON at: secrets/gee_service_account.json"
