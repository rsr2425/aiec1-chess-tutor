"""Unit tests for the parse_pgn node."""

import io
import pytest
import chess.pgn

from app.graphs.distillation import parse_pgn
from app.schemas import DistillationState


def _state(pgn: str) -> DistillationState:
    return DistillationState(
        user_id="test",
        game_id="g1",
        pgn=pgn,
        student_color="white",
    )


class TestParsePgn:
    def test_extracts_annotations(self, annotated_pgn: str):
        result = parse_pgn(_state(annotated_pgn))
        assert result["annotated"] is True
        assert len(result["annotations"]) > 0

    def test_annotations_have_text(self, annotated_pgn: str):
        result = parse_pgn(_state(annotated_pgn))
        for ann in result["annotations"]:
            assert ann.text.strip(), "Annotation text should not be empty"

    def test_annotations_have_plies(self, annotated_pgn: str):
        result = parse_pgn(_state(annotated_pgn))
        for ann in result["annotations"]:
            assert ann.ply >= 1

    def test_bare_game_detected(self, bare_pgn: str):
        result = parse_pgn(_state(bare_pgn))
        assert result["annotated"] is False
        assert result["annotations"] == []

    def test_annotation_plies_are_sequential(self, annotated_pgn: str):
        result = parse_pgn(_state(annotated_pgn))
        plies = [a.ply for a in result["annotations"]]
        assert plies == sorted(plies), "Annotation plies should be in order"

    def test_invalid_pgn_raises(self):
        with pytest.raises(Exception):
            parse_pgn(_state("this is not a pgn"))
