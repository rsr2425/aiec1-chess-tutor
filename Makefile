.PHONY: up down build setup test test-unit test-engine test-integration \
        logs logs-backend logs-engine logs-frontend \
        ingest fetch-games eval-retrieval eval-planted lint fmt \
        ps shell-backend shell-engine

# ── Quick aliases ──────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose up -d --build

restart:
	docker compose restart

ps:
	docker compose ps

# ── Local dev setup (run once, or after adding deps) ──────────────────────────
setup:
	cd src/backend && uv sync --extra dev
	cd src/chess-engine-server && uv sync --extra dev

# ── Tests ─────────────────────────────────────────────────────────────────────
# Run all local (no-Docker) unit tests
test: test-unit test-engine

test-unit:
	cd src/backend && uv run --extra dev pytest tests/unit/ -v

test-engine:
	cd src/chess-engine-server && uv run --extra dev pytest tests/unit/ -v

# Requires all containers to be running (make up first)
test-integration:
	docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from backend-test

# ── Logs ──────────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-engine:
	docker compose logs -f chess-engine-server

logs-frontend:
	docker compose logs -f frontend

# ── Shell access ──────────────────────────────────────────────────────────────
shell-backend:
	docker compose exec backend bash

shell-engine:
	docker compose exec chess-engine-server bash

# ── Data ingestion ────────────────────────────────────────────────────────────
ingest:
	docker compose run --rm backend uv run python ../../scripts/ingest_library.py

fetch-games:
	docker compose run --rm backend uv run python ../../scripts/fetch_lichess_games.py

# ── Evals ─────────────────────────────────────────────────────────────────────
eval-retrieval:
	docker compose run --rm backend uv run python ../../evals/retrieval_ragas.py

eval-planted:
	docker compose run --rm backend uv run python ../../evals/planted_mistakes/run.py

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	cd src/backend && uv run --extra dev ruff check .
	cd src/chess-engine-server && uv run --extra dev ruff check .

fmt:
	cd src/backend && uv run --extra dev ruff format .
	cd src/chess-engine-server && uv run --extra dev ruff format .
