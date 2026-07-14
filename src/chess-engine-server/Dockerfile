FROM python:3.13-slim

# Stockfish via apt; curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/games/stockfish /usr/local/bin/stockfish

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python deps (including optional maia2 when ENABLE_MAIA=true at build time)
# We always install the base deps; maia2 is imported lazily at runtime.
COPY pyproject.toml .
RUN uv pip install --system fastapi "uvicorn[standard]" python-chess httpx pydantic pydantic-settings

# Try to install maia2; if it fails (e.g., no torch wheels), skip it.
# ENABLE_MAIA env var at runtime controls whether we actually load it.
RUN uv pip install --system maia2 || echo "maia2 install skipped — Stockfish-only mode"

COPY . .

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8001/healthz || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
