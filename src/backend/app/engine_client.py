"""HTTP client for the Chess Engine Service.

Wraps the two endpoints the backend calls:
    POST /analyze/game      — distillation workhorse
    POST /analyze/position  — chat tool

Retries ×3 with exponential backoff to survive Render cold starts (~30s).
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx

from app.schemas import PlyResult

_BASE_URL = os.getenv("ENGINE_SERVICE_URL", "http://localhost:8001")
_TOKEN = os.getenv("ENGINE_SERVICE_TOKEN", "")

_RETRY_DELAYS = [5.0, 15.0, 30.0]  # seconds between retries


def _headers() -> dict:
    if _TOKEN:
        return {"Authorization": f"Bearer {_TOKEN}"}
    return {}


async def _post_with_retry(path: str, payload: dict) -> dict:
    last_exc: Exception = RuntimeError("No attempts made")
    async with httpx.AsyncClient(
        base_url=_BASE_URL,
        headers=_headers(),
        timeout=180.0,  # engine pass can take ~2 min on CPU
    ) as client:
        for attempt, delay in enumerate([0.0] + _RETRY_DELAYS, start=1):
            if delay:
                await asyncio.sleep(delay)
            try:
                r = await client.post(path, json=payload)
                r.raise_for_status()
                return r.json()
            except (httpx.HTTPError, httpx.ConnectError) as exc:
                last_exc = exc
                print(f"[engine_client] Attempt {attempt} failed: {exc}")
    raise last_exc


async def analyze_game(
    pgn: str,
    student_color: str = "white",
    student_rating: int = 1400,
    depth: int = 14,
    maia_top_k: int = 5,
) -> list[PlyResult]:
    """Call /analyze/game and return typed per-ply results."""
    data = await _post_with_retry(
        "/analyze/game",
        {
            "pgn": pgn,
            "student_color": student_color,
            "student_rating": student_rating,
            "depth": depth,
            "maia_top_k": maia_top_k,
        },
    )
    return [PlyResult.model_validate(p) for p in data["plies"]]


async def analyze_position(
    fen: str,
    student_rating: int = 1400,
    depth: int = 16,
) -> dict:
    """Call /analyze/position and return the raw response dict."""
    return await _post_with_retry(
        "/analyze/position",
        {
            "fen": fen,
            "student_rating": student_rating,
            "depth": depth,
        },
    )
