SHELL := /bin/sh
.DEFAULT_GOAL := help
COMPOSE := python3 scripts/manage.py compose
export UV_CACHE_DIR := $(CURDIR)/.uv-cache

.PHONY: help start demo doctor stop status logs bootstrap audit lock up down migrate ingest-once collect archive test test-unit test-integration test-contract test-features test-leakage e2e-collector e2e load-test data-audit data-readiness dashboard-backfill test-reporting-sql smoke demo-check lint format

help:
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

start: ## Configure and start the live app, then wait for real data
	python3 scripts/manage.py start

demo: ## Run the sample-data demo without Docker or PostgreSQL
	python3 scripts/manage.py demo

doctor: ## Diagnose Docker, Compose, configuration, and application status
	python3 scripts/manage.py doctor

stop: ## Stop this project's services while preserving collected data
	python3 scripts/manage.py stop

status: ## Show this project's running services
	python3 scripts/manage.py status

logs: ## Show recent application and collector diagnostics
	python3 scripts/manage.py logs

bootstrap: ## Create .env if absent and lock dependencies
	python3 scripts/manage.py setup
	uv sync --locked --group dev

audit: ## Print tool versions and validate configuration without secrets
	./scripts/audit.sh

lock: ## Resolve and update uv.lock
	uv lock

up: ## Start database, migrations, collector, and API
	python3 scripts/manage.py start

down: ## Stop local services without deleting volumes
	$(COMPOSE) down

migrate: ## Apply database migrations
	$(COMPOSE) run --rm migrate

ingest-once: ## Fetch and persist one live GBFS batch
	$(COMPOSE) run --rm collector bikeshare ingest-once

collect: ## Run the collector in the foreground
	$(COMPOSE) run --rm collector

archive: ## Export/verify expired history, then release database copies
	$(COMPOSE) --profile maintenance run --rm archive

test: ## Run all non-live tests in the tool container
	$(COMPOSE) --profile tools run --build --rm test

test-unit: ## Run deterministic unit tests
	uv run --locked --no-sync pytest tests/unit

test-integration: ## Run PostgreSQL integration tests
	uv run --locked --no-sync pytest -m integration tests/integration

test-contract: ## Run API contract tests
	uv run --locked --no-sync pytest tests/contract

test-features: ## Run feature and label tests
	uv run --locked --no-sync pytest tests/unit/test_features.py tests/unit/test_labels.py

test-leakage: ## Run point-in-time and split-boundary checks
	uv run --locked --no-sync pytest tests/unit/test_features.py -k point_in_time

e2e-collector: ## Exercise mocked collector failure and recovery paths
	uv run --locked --no-sync pytest tests/e2e/test_collector.py

e2e: ## Run application end-to-end checks
	uv run --locked --no-sync pytest tests/e2e

load-test: ## Run the fixed-seed local load scenario
	uv run --locked --no-sync python scripts/load_test.py

data-audit: ## Report database coverage and freshness
	$(COMPOSE) exec collector bikeshare data-audit

data-readiness: ## Evaluate, but never bypass, live-history model gates
	$(COMPOSE) exec collector bikeshare data-readiness

dashboard-backfill: ## Build dashboard aggregates from up to 31 days of retained real snapshots
	$(COMPOSE) exec collector bikeshare dashboard-backfill --days 31

test-reporting-sql: ## Verify reporting views and read-only grants
	uv run --locked --no-sync pytest -m integration tests/integration/test_reporting.py

smoke: ## Check health and one recommendation locally
	./scripts/smoke.sh

demo-check: ## Print the demo URL after checking readiness
	./scripts/demo_check.sh

lint: ## Run static checks
	uv run --locked --no-sync ruff check src tests alembic scripts
	uv run --locked --no-sync mypy

format: ## Format Python sources
	uv run --locked --no-sync ruff format .
