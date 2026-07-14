"""Pydantic schemas shared across graphs, tools, and the API layer."""

from __future__ import annotations

from typing import Optional, Literal
from uuid import uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, Field


# ── Engine service response types ─────────────────────────────────────────────


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
    best_line_san: list[str] = Field(default_factory=list)
    cp_loss: Optional[int] = None
    maia: Optional[MaiaData] = None


# ── Core domain types ─────────────────────────────────────────────────────────


class Annotation(BaseModel):
    """A student's written comment attached to a specific ply."""
    ply: int
    text: str


class Moment(BaseModel):
    """A key position singled out from a game — the unit of position-level recall."""
    ply: int
    fen: str
    move_san: str
    annotation: Optional[str] = None
    cp_loss: int
    best_move_san: Optional[str] = None
    maia_played_prob: Optional[float] = None
    description: str = ""  # LLM-written paragraph; populated by describe_moments node


class Takeaway(BaseModel):
    """One of the 2–3 distilled coaching points for a game."""
    text: str
    moment_ply: int


# ── Lesson (persistent, LangGraph Store) ─────────────────────────────────────


class LessonEvidence(BaseModel):
    game_id: str
    ply: int


class Lesson(BaseModel):
    """A recurring habit in the student's play — the tutor's long-term memory."""
    lesson_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    recurrence: int = 1
    status: Literal["active", "retired"] = "active"
    evidence: list[LessonEvidence] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Lesson operation types (output of the `distill` node) ────────────────────


class ReinforceLessonOp(BaseModel):
    op: Literal["reinforce"]
    lesson_id: str
    evidence: LessonEvidence


class CreateLessonOp(BaseModel):
    op: Literal["create"]
    name: str
    description: str
    evidence: LessonEvidence


class MergeLessonOp(BaseModel):
    op: Literal["merge"]
    lesson_ids: list[str]
    new_name: str
    new_description: str


class RenameLessonOp(BaseModel):
    op: Literal["rename"]
    lesson_id: str
    new_name: str


class RetireLessonOp(BaseModel):
    op: Literal["retire"]
    lesson_id: str


LessonOp = (
    ReinforceLessonOp
    | CreateLessonOp
    | MergeLessonOp
    | RenameLessonOp
    | RetireLessonOp
)


# ── Distillation graph output types ──────────────────────────────────────────


class DistillOutput(BaseModel):
    """Structured output from the `distill` LLM node."""
    takeaways: list[Takeaway] = Field(
        min_length=2,
        max_length=3,
        description="2–3 key coaching points grounded in this game and existing Lessons.",
    )
    lesson_ops: list[dict] = Field(
        default_factory=list,
        description="Lesson operations: reinforce | create | merge | rename | retire.",
    )


class GameSummary(BaseModel):
    """One paragraph describing a game — the unit of game-level recall."""
    game_id: str
    user_id: str
    date: str
    result: str
    opening: str
    takeaways: list[str]
    summary_text: str


# ── Chat agent types ──────────────────────────────────────────────────────────


class BoardRef(BaseModel):
    """A board position the tutor wants to show the student."""
    fen: str
    caption: str = ""


class TutorReply(BaseModel):
    """Structured response from the chat agent — the UI renders this directly."""
    reply: str = Field(description="Markdown coaching response shown in the chat panel.")
    positions: list[BoardRef] = Field(
        default_factory=list,
        description="Board positions referenced in the reply; each renders as a clickable chip.",
    )


# ── Distillation graph state ──────────────────────────────────────────────────


class DistillationState(BaseModel):
    """LangGraph state for the distillation pipeline."""
    # Inputs
    user_id: str
    game_id: str
    pgn: str
    student_color: str = "white"
    student_rating: int = 1400

    # Populated progressively by pipeline nodes
    annotations: list[Annotation] = Field(default_factory=list)
    annotated: bool = False
    plies: list[PlyResult] = Field(default_factory=list)
    moments: list[Moment] = Field(default_factory=list)
    takeaways: list[Takeaway] = Field(default_factory=list)
    summary: str = ""
    lessons_top10: list[Lesson] = Field(default_factory=list)
