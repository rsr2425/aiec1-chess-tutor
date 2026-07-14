"""Stockfish wrapper — per-game batch analysis and single-position analysis."""

from __future__ import annotations

import chess
import chess.engine
import chess.pgn
import io
from typing import Optional

MATE_CP = 10_000


def _cp(score: chess.engine.Score, pov: chess.Color) -> int:
    """Convert a Score to centipawns from *pov*'s perspective. Mate → ±MATE_CP."""
    relative = score.pov(pov)
    if relative.is_mate():
        return MATE_CP if (relative.mate() or 0) > 0 else -MATE_CP
    return relative.score() or 0


def analyze_game(
    pgn_text: str,
    student_color: str,
    depth: int = 14,
) -> list[dict]:
    """Analyze every ply in a PGN game and return per-ply data.

    Returns a list of dicts, one per ply, with the following keys:
        ply, san, uci, fen_before, fen_after,
        eval_before_cp, eval_after_cp,          # white POV
        best_move_uci, best_line_san,
        cp_loss,                                 # student POV; None for opponent plies
        maia                                     # always None here — populated by maia.py
    """
    color = chess.WHITE if student_color.lower() == "white" else chess.BLACK

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("Could not parse PGN")

    board = game.board()
    results: list[dict] = []

    with chess.engine.SimpleEngine.popen_uci("stockfish") as engine:
        node = game
        while node.variations:
            next_node = node.variations[0]
            move = next_node.move

            fen_before = board.fen()
            info_before = engine.analyse(board, chess.engine.Limit(depth=depth))
            eval_before_white = _cp(info_before["score"], chess.WHITE)
            best_move = info_before.get("pv", [None])[0]
            best_move_uci = best_move.uci() if best_move else None

            # Get the best continuation in SAN for the reply
            pv_moves = info_before.get("pv", [])[:5]
            temp_board = board.copy()
            best_line_san: list[str] = []
            for m in pv_moves:
                if temp_board.is_legal(m):
                    best_line_san.append(temp_board.san(m))
                    temp_board.push(m)

            san = board.san(move)
            board.push(move)
            fen_after = board.fen()

            info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
            eval_after_white = _cp(info_after["score"], chess.WHITE)

            # cp_loss: positive = student lost centipawns
            if board.turn != color:  # it was the student's turn before the push
                if color == chess.WHITE:
                    cp_loss = max(0, eval_before_white - eval_after_white)
                else:
                    cp_loss: Optional[int] = max(0, eval_after_white - eval_before_white)
            else:
                cp_loss = None

            results.append(
                {
                    "ply": len(results) + 1,
                    "san": san,
                    "uci": move.uci(),
                    "fen_before": fen_before,
                    "fen_after": fen_after,
                    "eval_before_cp": eval_before_white,
                    "eval_after_cp": eval_after_white,
                    "best_move_uci": best_move_uci,
                    "best_line_san": best_line_san,
                    "cp_loss": cp_loss,
                    "maia": None,
                }
            )
            node = next_node

    return results


def analyze_position(fen: str, depth: int = 16) -> dict:
    """Single-position analysis for the chat tool."""
    board = chess.Board(fen)

    with chess.engine.SimpleEngine.popen_uci("stockfish") as engine:
        info = engine.analyse(board, chess.engine.Limit(depth=depth))

    score = info["score"]
    eval_cp = _cp(score, chess.WHITE)

    pv = info.get("pv", [])
    best_move_san: Optional[str] = None
    best_line_san: list[str] = []

    if pv:
        temp = board.copy()
        best_move_san = temp.san(pv[0])
        for m in pv[:5]:
            if temp.is_legal(m):
                best_line_san.append(temp.san(m))
                temp.push(m)

    return {
        "eval_cp": eval_cp,
        "best_move_san": best_move_san,
        "best_line_san": best_line_san,
        "maia": None,
    }
