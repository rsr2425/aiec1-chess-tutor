"""Shared test fixtures for the backend."""

from uuid import uuid4
import pytest

# ── PGN fixtures ──────────────────────────────────────────────────────────────

ANNOTATED_PGN = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "0-1"]

1. e4 {I want to control the center.} e5 2. Nf3 Nc6 3. Bc4 {Developing and eyeing f7.} Bc5
4. b4 {The Evans Gambit — I thought this wins material.} Bxb4 5. c3 {I'll win the bishop back.} Ba5
6. d4 {Opening the center.} exd4 7. O-O {I thought castling was safe.} d3
8. Qb3 {I was trying to attack f7 and b7 at once.} Qf6?? {I thought I was defending.}
9. e5 Qg6 10. Re1 Nge7 11. Ba3 b5 12. Qxb5 Rb8 13. Qa4 Bb6 0-1
"""

BARE_PGN = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "0-1"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O d3
8. Qb3 Qf6 9. e5 Qg6 10. Re1 Nge7 11. Ba3 b5 12. Qxb5 Rb8 13. Qa4 Bb6 0-1
"""


@pytest.fixture
def annotated_pgn() -> str:
    return ANNOTATED_PGN


@pytest.fixture
def bare_pgn() -> str:
    return BARE_PGN


@pytest.fixture
def test_user_id() -> str:
    return f"test-user-{str(uuid4())[:8]}"


@pytest.fixture
def test_game_id() -> str:
    return f"test-game-{str(uuid4())[:8]}"
