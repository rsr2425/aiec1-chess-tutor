# ADR 0002 — Three-service deployment topology

**Status:** Accepted  
**Date:** 2026-07-08

## Context

The system requires:
1. A LangGraph agent with persistent memory (Lessons, chat threads).
2. Chess engine analysis (Stockfish + Maia-2), which requires native binaries
   and a CPU-heavy PyTorch dependency.
3. A web UI accessible from a browser and a phone.

Putting the engine inside the LangGraph agent image would require PyTorch in
the agent container, which conflicts with LangSmith's torch-free deployment
requirement and bloats the image.

## Decision

Split into three independently deployed services:

| Service | Host | Notes |
|---|---|---|
| LangGraph agent | LangSmith managed | torch-free image; managed checkpointer + Store |
| Next.js UI | Vercel | passthrough proxy; no secrets in browser |
| Engine Service | Render (CPU) | apt stockfish + pip maia2; stateless |

All communication is HTTP. The browser only ever talks to Vercel. All API keys
are server-side only.

## Consequences

- Maia-2 can be disabled via `ENABLE_MAIA=false` without touching the agent —
  the engine service returns `maia: null` and the agent treats it as optional.
- Dropping Maia-2 entirely is a config change, not a code change.
- Cold starts on Render (~30s on first request) are handled by the agent's
  retry logic in `engine_client.py` (×3 with exponential backoff).
- Local development mirrors production topology via Docker Compose.
