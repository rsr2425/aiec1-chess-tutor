"""Unit tests for the Stockfish wrapper — no network, stockfish binary required."""

import shutil
import pytest
import chess
import chess.pgn
import io

from engine.stockfish import analyze_game, analyze_position, MATE_CP

stockfish_available = pytest.mark.skipif(
    shutil.which("stockfish") is None,
    reason="stockfish binary not found — run these in Docker (make test-integration)",
)

SCHOLARS_MATE_PGN = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6?? 4. Qxf7# 1-0
"""


class TestAnalyzeGame:
    @stockfish_available
    def test_ply_count_matches_moves(self):
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="white")
        # 7 half-moves: White plays 4, Black plays 3 (no reply after Qxf7#)
        assert len(result) == 7

    @stockfish_available
    def test_ply_numbers_are_sequential(self):
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="white")
        assert [r["ply"] for r in result] == list(range(1, len(result) + 1))

    @stockfish_available
    def test_cp_loss_only_on_student_plies_white(self):
        """When student is White, cp_loss is set on odd plies (White's turns)."""
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="white")
        white_plies = [r for r in result if r["cp_loss"] is not None]
        black_plies = [r for r in result if r["cp_loss"] is None]
        assert len(white_plies) > 0
        assert len(black_plies) > 0
        for r in white_plies:
            assert r["ply"] % 2 == 1, f"Expected odd ply for White, got {r['ply']}"

    @stockfish_available
    def test_cp_loss_only_on_student_plies_black(self):
        """When student is Black, cp_loss is set on even plies (Black's turns)."""
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="black")
        black_plies = [r for r in result if r["cp_loss"] is not None]
        for r in black_plies:
            assert r["ply"] % 2 == 0, f"Expected even ply for Black, got {r['ply']}"

    @stockfish_available
    def test_cp_loss_is_non_negative(self):
        """cp_loss is never negative — it represents centipawns lost, not gained."""
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="white")
        for r in result:
            if r["cp_loss"] is not None:
                assert r["cp_loss"] >= 0

    @stockfish_available
    def test_fen_fields_are_valid(self):
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="white")
        for r in result:
            chess.Board(r["fen_before"])
            chess.Board(r["fen_after"])

    @stockfish_available
    def test_san_and_uci_fields_present(self):
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="white")
        for r in result:
            assert r["san"], f"Empty SAN at ply {r['ply']}"
            assert len(r["uci"]) >= 4, f"Invalid UCI at ply {r['ply']}"

    @stockfish_available
    def test_maia_is_null(self):
        """Stockfish wrapper never populates maia — that's main.py's job."""
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="white")
        for r in result:
            assert r["maia"] is None

    @stockfish_available
    def test_final_position_is_checkmate(self):
        """After the Scholar's Mate the last fen_after should be checkmate."""
        result = analyze_game(SCHOLARS_MATE_PGN, student_color="white")
        last_fen = result[-1]["fen_after"]
        board = chess.Board(last_fen)
        assert board.is_checkmate()

    def test_invalid_pgn_raises(self):
        with pytest.raises(Exception):
            analyze_game("not a pgn", student_color="white")


class TestAnalyzePosition:
    START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    @stockfish_available
    def test_returns_expected_keys(self):
        result = analyze_position(self.START_FEN)
        assert "eval_cp" in result
        assert "best_move_san" in result
        assert "best_line_san" in result
        assert "maia" in result

    @stockfish_available
    def test_eval_is_near_zero_for_start_position(self):
        """Starting position eval should be small (roughly ±50 cp)."""
        result = analyze_position(self.START_FEN)
        assert abs(result["eval_cp"]) < 100

    @stockfish_available
    def test_best_move_is_a_string(self):
        result = analyze_position(self.START_FEN)
        assert isinstance(result["best_move_san"], str)
        assert len(result["best_move_san"]) >= 2

    @stockfish_available
    def test_best_line_is_list(self):
        result = analyze_position(self.START_FEN)
        assert isinstance(result["best_line_san"], list)
        assert len(result["best_line_san"]) >= 1

    @stockfish_available
    def test_maia_is_null_from_wrapper(self):
        result = analyze_position(self.START_FEN)
        assert result["maia"] is None

    @stockfish_available
    def test_mate_position_returns_max_cp(self):
        """Scholar's Mate position — eval should be MATE_CP."""
        mate_fen = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"
        result = analyze_position(mate_fen)
        assert result["eval_cp"] == MATE_CP
