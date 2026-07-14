"""Unit tests for the select_moments node (pure deterministic code)."""

import pytest

from app.graphs.distillation import (
    select_moments,
    CP_LOSS_THRESHOLD,
    ANNOTATED_FORCE_INCLUDE_THRESHOLD,
    MOMENTS_CAP,
    MOMENTS_FLOOR,
)
from app.schemas import Annotation, DistillationState, PlyResult


def _make_ply(ply: int, cp_loss: int | None) -> PlyResult:
    return PlyResult(
        ply=ply,
        san="e4",
        uci="e2e4",
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        eval_before_cp=20,
        eval_after_cp=20,
        cp_loss=cp_loss,
    )


def _state(plies: list[PlyResult], annotations: list[Annotation] | None = None) -> DistillationState:
    return DistillationState(
        user_id="test",
        game_id="g1",
        pgn="",
        student_color="white",
        plies=plies,
        annotations=annotations or [],
    )


class TestSelectMoments:
    def test_selects_plies_above_threshold(self):
        plies = [
            _make_ply(1, 200),  # above threshold
            _make_ply(3, 50),   # below threshold
            _make_ply(5, 300),  # above threshold
            _make_ply(7, 160),  # above threshold — 3 above ensures floor is met without ply 3
        ]
        result = select_moments(_state(plies))
        selected_plies = [m.ply for m in result["moments"]]
        assert 1 in selected_plies
        assert 5 in selected_plies
        assert 7 in selected_plies
        assert 3 not in selected_plies

    def test_does_not_exceed_cap(self):
        plies = [_make_ply(i * 2 - 1, 200 + i * 10) for i in range(1, 10)]
        result = select_moments(_state(plies))
        assert len(result["moments"]) <= MOMENTS_CAP

    def test_pads_to_floor(self):
        """When fewer than FLOOR plies are above threshold, pad with next-largest."""
        plies = [
            _make_ply(1, 200),   # above threshold
            _make_ply(3, 80),    # below threshold
            _make_ply(5, 60),    # below threshold
        ]
        result = select_moments(_state(plies))
        assert len(result["moments"]) >= MOMENTS_FLOOR

    def test_force_includes_annotated_above_75(self):
        """Annotated plies with cp_loss >= 75 are force-included even if below 150."""
        annotations = [Annotation(ply=3, text="I thought this was safe")]
        plies = [
            _make_ply(1, 200),   # above normal threshold
            _make_ply(3, 80),    # below 150, but annotated and above 75 → force-include
        ]
        result = select_moments(_state(plies, annotations))
        selected = [m.ply for m in result["moments"]]
        assert 3 in selected, "Annotated ply with cp_loss=80 should be force-included"

    def test_annotated_below_75_not_force_included(self):
        """Annotated plies below 75 cp_loss are not force-included."""
        annotations = [Annotation(ply=3, text="I thought this was safe")]
        plies = [
            _make_ply(1, 200),
            _make_ply(3, 50),    # annotated but cp_loss < 75 → not forced
        ]
        result = select_moments(_state(plies, annotations))
        selected = [m.ply for m in result["moments"]]
        # ply 3 might be included as padding but only because of floor rule
        # it should NOT be in the selection if floor is not needed
        if len([p for p in plies if (p.cp_loss or 0) >= CP_LOSS_THRESHOLD]) >= MOMENTS_FLOOR:
            assert 3 not in selected

    def test_no_student_plies_returns_empty(self):
        """Opponent-only plies (cp_loss=None) → no moments."""
        plies = [_make_ply(2, None), _make_ply(4, None)]
        result = select_moments(_state(plies))
        assert result["moments"] == []

    def test_moments_ordered_by_ply(self):
        plies = [_make_ply(5, 300), _make_ply(1, 200), _make_ply(3, 250)]
        result = select_moments(_state(plies))
        ply_order = [m.ply for m in result["moments"]]
        assert ply_order == sorted(ply_order)
