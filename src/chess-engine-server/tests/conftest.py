"""Shared fixtures for chess-engine-server tests."""

import os
import pytest
import httpx

# Scholar's Mate — 4 moves, White wins by checkmate.
# Useful because the result (mate) is verifiable and the game is short.
SCHOLARS_MATE_PGN = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6?? 4. Qxf7# 1-0
"""

# A slightly longer game where Black blunders on move 6 (loses a piece)
# so cp_loss for Black is large and positive from Black's POV.
BLUNDER_PGN = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O d3 8. Qb3 Qf6 9. e5 Qg6 10. Re1 Nge7 11. Ba3 b5 12. Qxb5 Rb8 13. Qa4 Bb6 14. Nbd2 Bb7 15. Ne4 Qf5 16. Bxd3 Qh5 17. Nf6+ gxf6 18. exf6 Rg8 1-0
"""


@pytest.fixture
def scholars_mate_pgn() -> str:
    return SCHOLARS_MATE_PGN


@pytest.fixture
def blunder_pgn() -> str:
    return BLUNDER_PGN


@pytest.fixture
def engine_base_url() -> str:
    return os.getenv("ENGINE_SERVICE_URL", "http://localhost:8001")


@pytest.fixture
async def async_client(engine_base_url: str):
    async with httpx.AsyncClient(base_url=engine_base_url, timeout=120.0) as client:
        yield client
