.PHONY: help bootstrap up down logs build test test-unit test-integration migrate lock fmt lint

DC := docker compose

help:
	@echo "Targets:"
	@echo "  bootstrap     generate .env from template (if missing), build, run migrations"
	@echo "  up            docker compose up -d"
	@echo "  down          docker compose down"
	@echo "  logs          tail logs from all services"
	@echo "  build         rebuild backend images"
	@echo "  migrate       run alembic upgrade head inside api container"
	@echo "  test          run all backend tests"
	@echo "  test-unit     run unit tests only"
	@echo "  test-integration  run integration tests (requires docker)"
	@echo "  lock          poetry lock --no-update"
	@echo "  fmt           ruff format"
	@echo "  lint          ruff check + mypy"

bootstrap:
	@bash infra/scripts/bootstrap.sh

up:
	$(DC) up -d

down:
	$(DC) down

logs:
	$(DC) logs -f --tail=100

build:
	$(DC) build api ingester

migrate:
	$(DC) exec api alembic upgrade head

test:
	cd backend && poetry run pytest -q

test-unit:
	cd backend && poetry run pytest tests/unit -q

test-integration:
	cd backend && poetry run pytest tests/integration -q

lock:
	cd backend && poetry lock --no-update

fmt:
	cd backend && poetry run ruff format src tests

lint:
	cd backend && poetry run ruff check src tests && poetry run mypy src
