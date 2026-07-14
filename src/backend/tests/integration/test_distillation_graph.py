"""Integration tests for the distillation graph.

Requires chess-engine-server and Qdrant running (docker-compose.test.yml).
LLM calls are replaced with FakeListChatModel to avoid real API costs.
"""

import pytest
from langchain_core.language_models.fake import FakeListChatModel
from unittest.mock import AsyncMock, patch

from app.graphs.distillation import parse_pgn, select_moments
from app.schemas import DistillationState

pytestmark = pytest.mark.asyncio

# A canned Moment description paragraph (returned by FakeListChatModel)
FAKE_DESCRIPTION = (
    "On move 8, the student played Qf6 after thinking they were defending. "
    "The queen sortie exposed it to tempo-gaining attacks. "
    "Stockfish recommends Qe7 instead, keeping the queen safe while developing."
)

FAKE_DISTILL_JSON = """{
  "takeaways": [
    {"text": "The queen was activated too early, allowing White to gain tempi.", "moment_ply": 15},
    {"text": "Overlooked the pin on the bishop when calculating the trade.", "moment_ply": 9}
  ],
  "lesson_ops": [
    {"op": "create", "name": "Early queen sorties", "description": "Student moves the queen early and loses time to attacks.", "evidence": {"game_id": "test-game", "ply": 15}}
  ]
}"""

FAKE_SUMMARY = (
    "This game opened with the Evans Gambit where the student, playing Black, "
    "accepted the pawn but then mishandled the position. The critical mistake "
    "came on move 8 when the queen was activated prematurely. The student lost material "
    "and resigned on move 13. Key lessons: avoid early queen sortie, verify pin before trading."
)


class TestDistillationNodes:
    """Test individual nodes in isolation."""

    def test_parse_pgn_with_annotated_game(self, annotated_pgn: str):
        state = DistillationState(
            user_id="u1", game_id="g1", pgn=annotated_pgn, student_color="black"
        )
        result = parse_pgn(state)
        assert result["annotated"] is True
        assert len(result["annotations"]) >= 3

    def test_parse_pgn_with_bare_game(self, bare_pgn: str):
        state = DistillationState(
            user_id="u1", game_id="g1", pgn=bare_pgn, student_color="black"
        )
        result = parse_pgn(state)
        assert result["annotated"] is False
        assert result["annotations"] == []

    def test_select_moments_from_engine_output(self, annotated_pgn: str):
        """select_moments works when given real-looking PlyResult data."""
        from app.schemas import PlyResult, Annotation

        plies = []
        for i in range(1, 27):  # 26 half-moves
            cp_loss = None
            if i % 2 == 0:  # Black's moves
                if i == 16:
                    cp_loss = 280  # big blunder
                elif i == 8:
                    cp_loss = 90  # annotated blunder
                else:
                    cp_loss = 10
            plies.append(
                PlyResult(
                    ply=i, san="e4", uci="e2e4",
                    fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    eval_before_cp=20, eval_after_cp=20, cp_loss=cp_loss,
                )
            )

        annotations = [Annotation(ply=8, text="I thought this was safe")]
        state = DistillationState(
            user_id="u1", game_id="g1", pgn=annotated_pgn, student_color="black",
            plies=plies, annotations=annotations,
        )
        result = select_moments(state)
        moments = result["moments"]

        # Ply 16 should be included (big blunder)
        assert any(m.ply == 16 for m in moments)
        # Ply 8 should be included (annotated + cp_loss=90 >= 75)
        assert any(m.ply == 8 for m in moments)
