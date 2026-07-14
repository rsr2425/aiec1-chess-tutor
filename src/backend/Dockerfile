FROM python:3.13-slim

# curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
RUN uv pip install --system \
    langgraph "langgraph-cli[inmem]" \
    langchain langchain-openai langchain-community langchain-qdrant langchain-tavily \
    qdrant-client python-chess httpx pydantic pydantic-settings tiktoken

COPY . .

EXPOSE 8000

# LangGraph dev server (in-memory mode — no external Postgres needed locally)
# TODO: remove --allow-blocking once Qdrant upserts use the async client
CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "8000", "--no-browser", "--allow-blocking"]
