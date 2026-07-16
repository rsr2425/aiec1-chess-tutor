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

# ── Data ingestion ─────────────────────────────────────────────────────────────
# Run from the host against local Qdrant by default. For Qdrant Cloud:
#   make ingest QDRANT_URL=https://<cluster>.cloud.qdrant.io:6333 QDRANT_API_KEY=<key>
QDRANT_URL ?= http://localhost:6333
QDRANT_API_KEY ?=

ingest:
	cd src/backend && set -a && . ../../.env && set +a && \
		QDRANT_URL="$(QDRANT_URL)" QDRANT_API_KEY="$(QDRANT_API_KEY)" \
		uv run python ../../scripts/ingest_library.py

fetch-games:
	cd src/backend && set -a && . ../../.env && set +a && \
		uv run --extra eval python ../../scripts/fetch_lichess_games.py

# ── Evals ─────────────────────────────────────────────────────────────────────
RETRIEVER ?= baseline

eval-retrieval:
	cd src/backend && set -a && . ../../.env && set +a && \
		QDRANT_URL="$(QDRANT_URL)" QDRANT_API_KEY="$(QDRANT_API_KEY)" RETRIEVER="$(RETRIEVER)" \
		uv run --extra eval python ../../evals/retrieval_ragas.py

eval-planted:
	cd src/backend && set -a && . ../../.env && set +a && \
		QDRANT_URL="$(QDRANT_URL)" QDRANT_API_KEY="$(QDRANT_API_KEY)" \
		uv run --extra eval python ../../evals/planted_mistakes/run.py

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	cd src/backend && uv run --extra dev ruff check .
	cd src/chess-engine-server && uv run --extra dev ruff check .

fmt:
	cd src/backend && uv run --extra dev ruff format .
	cd src/chess-engine-server && uv run --extra dev ruff format .
