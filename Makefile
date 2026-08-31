PNPM ?= npx -y pnpm
PYTHON ?= python3
PIP ?= pip

.PHONY: install dev build test test-e2e lint validate-schemas db-up db-down help

help:
	@echo "OpenRobo Monorepo Commands:"
	@echo "  make install           - Install all dependencies (Node & Python)"
	@echo "  make lint              - Run linter checks (Python ruff, JS eslint)"
	@echo "  make validate-schemas  - Validate JSON schemas"
	@echo "  make test              - Run all backend and frontend unit tests"
	@echo "  make test-e2e          - Run Playwright E2E browser tests"
	@echo "  make build             - Build web frontend and check packages"
	@echo "  make db-up             - Start local PostgreSQL 16 container"
	@echo "  make db-down           - Stop local PostgreSQL container"

install:
	$(PNPM) install
	$(PIP) install -e packages/schemas
	$(PIP) install -e packages/compat-engine
	$(PIP) install -e packages/cli
	$(PIP) install -e apps/api

lint:
	ruff check .
	$(PNPM) lint

validate-schemas:
	$(PYTHON) scripts/validate_schemas.py

test: validate-schemas
	PYTHONPATH=. pytest -p no:launch_testing_ros_pytest_entrypoint -p no:launch_testing_ros
	$(PNPM) --filter openrobo-web test

test-e2e:
	$(PNPM) --filter openrobo-web test:e2e

build:
	$(PNPM) --recursive run build

db-up:
	docker compose up -d postgres

db-down:
	docker compose down
