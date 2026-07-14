"""Chess Engine Service — FastAPI app.

Endpoints:
    GET  /healthz               health check
    POST /analyze/game          full-game analysis (distillation workhorse)
    POST /analyze/position      single-position analysis (chat tool)
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

from engine import stockfish, maia

app = FastAPI(title="Chess Engine Service", version="0.1.0")

_TOKEN = os.getenv("ENGINE_SERVICE_TOKEN", "")


def _check_auth(authorization: Optional[str]) -> None:
    if not _TOKEN:
        return
    if authorization != f"Bearer {_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Request / Response models ─────────────────────────────────────────────────


class AnalyzeGameRequest(BaseModel):
    pgn: str
    student_color: str = "white"
    student_rating: int = Field(default=1400, ge=100, le=3000)
    depth: int = Field(default=14, ge=1, le=30)
    maia_top_k: int = Field(default=5, ge=1, le=20)


class MaiaData(BaseModel):
    top_moves: list[dict]
    played_prob: Optional[float] = None
    win_prob: float


class PlyResult(BaseModel):
    ply: int
    san: str
    uci: str
    fen_before: str
    fen_after: str
    eval_before_cp: int
    eval_after_cp: int
    best_move_uci: Optional[str] = None
    best_line_san: list[str] = []
    cp_loss: Optional[int] = None
    maia: Optional[MaiaData] = None


class AnalyzeGameResponse(BaseModel):
    plies: list[PlyResult]


class AnalyzePositionRequest(BaseModel):
    fen: str
    student_rating: int = Field(default=1400, ge=100, le=3000)
    depth: int = Field(default=16, ge=1, le=30)


class AnalyzePositionResponse(BaseModel):
    eval_cp: int
    best_move_san: Optional[str] = None
    best_line_san: list[str] = []
    maia: Optional[dict] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/analyze/game", response_model=AnalyzeGameResponse)
async def analyze_game(
    req: AnalyzeGameRequest,
    authorization: Optional[str] = Header(default=None),
) -> AnalyzeGameResponse:
    _check_auth(authorization)

    try:
        plies = stockfish.analyze_game(
            pgn_text=req.pgn,
            student_color=req.student_color,
            depth=req.depth,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Enrich student plies with Maia data where available
    for ply in plies:
        if ply["cp_loss"] is not None:  # student's ply
            maia_pos = maia.analyze_position(
                ply["fen_before"],
                student_rating=req.student_rating,
                top_k=req.maia_top_k,
            )
            if maia_pos is not None:
                played_prob = maia.get_played_prob(
                    ply["fen_before"],
                    ply["uci"],
                    student_rating=req.student_rating,
                )
                ply["maia"] = MaiaData(
                    top_moves=maia_pos["top_moves"],
                    played_prob=played_prob,
                    win_prob=maia_pos["win_prob"],
                )

    return AnalyzeGameResponse(plies=[PlyResult(**p) for p in plies])


@app.post("/analyze/position", response_model=AnalyzePositionResponse)
async def analyze_position(
    req: AnalyzePositionRequest,
    authorization: Optional[str] = Header(default=None),
) -> AnalyzePositionResponse:
    _check_auth(authorization)

    try:
        result = stockfish.analyze_position(req.fen, depth=req.depth)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    maia_data = maia.analyze_position(req.fen, student_rating=req.student_rating)

    return AnalyzePositionResponse(
        eval_cp=result["eval_cp"],
        best_move_san=result["best_move_san"],
        best_line_san=result["best_line_san"],
        maia=maia_data,
    )
