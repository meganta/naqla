.PHONY: dev test lint build format

dev:
	docker compose up --build

dev-down:
	docker compose down -v

lint:
	cd apps/api && uv run ruff check .
	cd services/worker && uv run ruff check .
	cd apps/frontend && pnpm lint

format:
	cd apps/api && uv run ruff format .
	cd services/worker && uv run ruff format .

typecheck:
	cd apps/api && uv run mypy .
	cd services/worker && uv run mypy .
	cd apps/frontend && pnpm typecheck

test:
	cd apps/api && uv run pytest tests/ -v
	cd services/worker && uv run pytest tests/ -v

build:
	docker build -t naqla-api:local apps/api
	docker build -t naqla-worker:local services/worker
	docker build -t naqla-frontend:local apps/frontend

migrate:
	cd apps/api && uv run alembic upgrade head

migrate-create:
	cd apps/api && uv run alembic revision --autogenerate -m "$(name)"
