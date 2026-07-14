"""Distillation subgraph — linear pipeline, no conditional edges.

Nodes (in order):
    parse_pgn          pure Python: extract moves + Annotations; detect Bare Game
    engine_pass        HTTP call to Engine Service (with retry)
    select_moments     pure Python: deterministic moment selection
    describe_moments   LLM: write one paragraph per Moment
    distill            LLM: produce Takeaways + LessonOps
    summarize_and_index LLM: write Game Summary, embed + upsert to Qdrant
"""

from __future__ import annotations

import io
import json
import os
from typing import Any
from uuid import uuid4

import chess.pgn
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from app import lessons as lesson_store
from app.engine_client import analyze_game as engine_analyze_game
from app.prompts import DESCRIBE_MOMENT_SYSTEM, DISTILL_SYSTEM, SUMMARIZE_SYSTEM
from app.retrieval import upsert_moment, upsert_game_summary
from app.schemas import (
    Annotation,
    DistillationState,
    Moment,
    PlyResult,
    Takeaway,
)

_DISTILL_MODEL = os.getenv("DISTILL_MODEL", "openai/gpt-4.1-mini")
_AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "")
_AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL", "")

# Moment selection thresholds (TDD §5, D3)
CP_LOSS_THRESHOLD = 150
ANNOTATED_FORCE_INCLUDE_THRESHOLD = 75
MOMENTS_CAP = 6
MOMENTS_FLOOR = 3


def _llm() -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": _DISTILL_MODEL,
        "api_key": _AI_GATEWAY_API_KEY,
        "temperature": 0,
    }
    if _AI_GATEWAY_BASE_URL:
        kwargs["base_url"] = _AI_GATEWAY_BASE_URL + "/v1"
    return ChatOpenAI(**kwargs)


# ── Node 1: parse_pgn ─────────────────────────────────────────────────────────


def parse_pgn(state: DistillationState) -> dict:
    game = chess.pgn.read_game(io.StringIO(state.pgn))
    if game is None or not game.variations:
        raise ValueError("Could not parse PGN or game has no moves")

    annotations: list[Annotation] = []
    node = game
    ply = 0
    while node.variations:
        next_node = node.variations[0]
        ply += 1
        comment = next_node.comment.strip()
        if comment:
            annotations.append(Annotation(ply=ply, text=comment))
        node = next_node

    annotated = len(annotations) > 0
    return {"annotations": annotations, "annotated": annotated}


# ── Node 2: engine_pass ───────────────────────────────────────────────────────


async def engine_pass(state: DistillationState) -> dict:
    plies = await engine_analyze_game(
        pgn=state.pgn,
        student_color=state.student_color,
        student_rating=state.student_rating,
    )
    return {"plies": plies}


# ── Node 3: select_moments ────────────────────────────────────────────────────


def select_moments(state: DistillationState) -> dict:
    """Pure deterministic selection — no LLM. (TDD D3)

    Rules:
    1. Force-include annotated plies with cp_loss >= ANNOTATED_FORCE_INCLUDE_THRESHOLD.
    2. Of remaining plies with cp_loss >= CP_LOSS_THRESHOLD, add highest first.
    3. Cap total at MOMENTS_CAP; pad up to MOMENTS_FLOOR with next-largest swings.
    """
    annotation_map = {a.ply: a.text for a in state.annotations}
    student_plies = [p for p in state.plies if p.cp_loss is not None]

    # Step 1: force-include annotated blunders
    force_included: set[int] = set()
    for p in student_plies:
        if p.ply in annotation_map and (p.cp_loss or 0) >= ANNOTATED_FORCE_INCLUDE_THRESHOLD:
            force_included.add(p.ply)

    # Step 2: candidates above threshold, sorted by cp_loss descending
    candidates = sorted(
        [p for p in student_plies if (p.cp_loss or 0) >= CP_LOSS_THRESHOLD],
        key=lambda p: p.cp_loss or 0,
        reverse=True,
    )
    selected_plies: list[int] = list(force_included)
    for p in candidates:
        if p.ply not in selected_plies and len(selected_plies) < MOMENTS_CAP:
            selected_plies.append(p.ply)

    # Step 3: pad to floor if needed
    if len(selected_plies) < MOMENTS_FLOOR:
        extras = sorted(
            [p for p in student_plies if p.ply not in selected_plies],
            key=lambda p: p.cp_loss or 0,
            reverse=True,
        )
        for p in extras:
            if len(selected_plies) >= MOMENTS_FLOOR:
                break
            selected_plies.append(p.ply)

    ply_map = {p.ply: p for p in state.plies}
    moments = [
        Moment(
            ply=ply_num,
            fen=ply_map[ply_num].fen_before,
            move_san=ply_map[ply_num].san,
            annotation=annotation_map.get(ply_num),
            cp_loss=ply_map[ply_num].cp_loss or 0,
            best_move_san=ply_map[ply_num].best_move_uci,
            maia_played_prob=(
                ply_map[ply_num].maia.played_prob
                if ply_map[ply_num].maia
                else None
            ),
        )
        for ply_num in sorted(selected_plies)
        if ply_num in ply_map
    ]

    return {"moments": moments}


# ── Node 4: describe_moments ──────────────────────────────────────────────────


async def describe_moments(state: DistillationState) -> dict:
    llm = _llm()
    annotated_flag = state.annotated

    described: list[Moment] = []
    for moment in state.moments:
        annotation_context = (
            f'Student\'s thinking: "{moment.annotation}"'
            if moment.annotation
            else "No annotation (student did not comment on this move)."
            if annotated_flag
            else "Bare game — no student annotations available."
        )
        prompt = (
            f"Position FEN: {moment.fen}\n"
            f"Move played: {moment.move_san}\n"
            f"{annotation_context}\n"
            f"Centipawn loss: {moment.cp_loss}\n"
            f"Engine's best move: {moment.best_move_san or 'unknown'}\n"
            "Write a concise analytical paragraph describing this mistake."
        )
        response = await llm.ainvoke(
            [{"role": "system", "content": DESCRIBE_MOMENT_SYSTEM},
             {"role": "user", "content": prompt}]
        )
        described.append(moment.model_copy(update={"description": response.content}))

    return {"moments": described}


# ── Node 5: distill ───────────────────────────────────────────────────────────


async def distill(state: DistillationState, store) -> dict:
    # Fetch the student's current top Lessons
    current_lessons = await lesson_store.top(store, state.user_id, n=10)

    lessons_text = ""
    if current_lessons:
        lines = [
            f"- [{l.lesson_id}] {l.name} (recurrence: {l.recurrence}): {l.description}"
            for l in current_lessons
        ]
        lessons_text = "Existing Lessons:\n" + "\n".join(lines)
    else:
        lessons_text = "Existing Lessons: none yet."

    moments_text = "\n\n".join(
        f"Ply {m.ply} ({m.move_san}, -{m.cp_loss}cp):\n{m.description}"
        for m in state.moments
    )

    prompt = f"{lessons_text}\n\nGame ID: {state.game_id}\n\nMoments:\n{moments_text}"

    llm = _llm()
    response = await llm.ainvoke(
        [{"role": "system", "content": DISTILL_SYSTEM},
         {"role": "user", "content": prompt}]
    )

    try:
        output = json.loads(response.content)
    except json.JSONDecodeError:
        # Malformed JSON — return minimal output rather than crashing
        output = {"takeaways": [], "lesson_ops": []}

    # Apply lesson ops (errors inside are caught per-op)
    await lesson_store.apply_ops(store, state.user_id, output.get("lesson_ops", []))

    takeaways = [Takeaway(**t) for t in output.get("takeaways", [])]
    updated_lessons = await lesson_store.top(store, state.user_id, n=10)

    return {"takeaways": takeaways, "lessons_top10": updated_lessons}


# ── Node 6: summarize_and_index ───────────────────────────────────────────────


async def summarize_and_index(state: DistillationState) -> dict:
    llm = _llm()

    takeaway_text = "\n".join(f"- {t.text}" for t in state.takeaways)
    moments_text = "\n".join(f"- Ply {m.ply}: {m.description[:200]}" for m in state.moments)

    summary_prompt = (
        f"Game ID: {state.game_id}\n"
        f"Student plays: {state.student_color}\n"
        f"Takeaways:\n{takeaway_text}\n\n"
        f"Key moments:\n{moments_text}"
    )

    response = await llm.ainvoke(
        [{"role": "system", "content": SUMMARIZE_SYSTEM},
         {"role": "user", "content": summary_prompt}]
    )
    summary_text = response.content

    # Upsert each Moment to Qdrant
    for moment in state.moments:
        doc = Document(
            page_content=moment.description,
            metadata={
                "user_id": state.user_id,
                "game_id": state.game_id,
                "ply": moment.ply,
                "fen": moment.fen,
                "move_san": moment.move_san,
                "annotation": moment.annotation,
                "cp_loss": moment.cp_loss,
                "best_move_san": moment.best_move_san,
                "maia_played_prob": moment.maia_played_prob,
            },
        )
        upsert_moment(doc)

    # Upsert Game Summary to Qdrant
    summary_doc = Document(
        page_content=summary_text,
        metadata={
            "user_id": state.user_id,
            "game_id": state.game_id,
            "takeaways": [t.text for t in state.takeaways],
        },
    )
    upsert_game_summary(summary_doc)

    return {"summary": summary_text}


# ── Graph assembly ────────────────────────────────────────────────────────────


builder = StateGraph(DistillationState)

builder.add_node("parse_pgn", parse_pgn)
builder.add_node("engine_pass", engine_pass)
builder.add_node("select_moments", select_moments)
builder.add_node("describe_moments", describe_moments)
builder.add_node("distill", distill)
builder.add_node("summarize_and_index", summarize_and_index)

builder.add_edge(START, "parse_pgn")
builder.add_edge("parse_pgn", "engine_pass")
builder.add_edge("engine_pass", "select_moments")
builder.add_edge("select_moments", "describe_moments")
builder.add_edge("describe_moments", "distill")
builder.add_edge("distill", "summarize_and_index")
builder.add_edge("summarize_and_index", END)

graph = builder.compile()
