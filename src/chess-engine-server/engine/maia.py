"""Maia-2 wrapper — nullable. Controlled by ENABLE_MAIA env var.

When ENABLE_MAIA=false (or maia2 fails to import), every function returns None
so callers stay unchanged.
"""

from __future__ import annotations

import os
from typing import Optional

_ENABLED = os.getenv("ENABLE_MAIA", "true").lower() == "true"
_model = None  # loaded lazily on first call


def _load() -> bool:
    """Try to load the Maia-2 model. Returns True on success."""
    global _model
    if _model is not None:
        return True
    if not _ENABLED:
        return False
    try:
        import maia2  # type: ignore

        _model = maia2.load()
        return True
    except Exception:
        return False


def analyze_position(
    fen: str,
    student_rating: int = 1400,
    top_k: int = 5,
) -> Optional[dict]:
    """Return Maia-2 move probabilities for *fen*, or None if unavailable."""
    if not _load():
        return None
    try:
        import chess

        board = chess.Board(fen)
        result = _model.predict(board, rating=student_rating, top_k=top_k)
        return {
            "top_moves": [
                {"uci": m.uci(), "prob": float(p)}
                for m, p in zip(result.moves, result.probs)
            ],
            "win_prob": float(result.win_prob),
        }
    except Exception:
        return None


def get_played_prob(
    fen: str,
    played_uci: str,
    student_rating: int = 1400,
) -> Optional[float]:
    """Return the probability Maia-2 assigns to the move the student actually played."""
    data = analyze_position(fen, student_rating)
    if data is None:
        return None
    for entry in data["top_moves"]:
        if entry["uci"] == played_uci:
            return entry["prob"]
    return 0.0
