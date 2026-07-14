"""Lesson store operations — the coach's notebook.

All state lives in the LangGraph cross-thread Store, namespaced by user_id.
This module provides verb-level functions that the distillation graph calls
after the LLM produces lesson_ops.

Judgment is in the model; bookkeeping is here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.schemas import Lesson, LessonEvidence

if TYPE_CHECKING:
    from langgraph.store.base import BaseStore


_NS = "lessons"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _namespace(user_id: str) -> tuple[str, str]:
    return (user_id, _NS)


# ── Read ──────────────────────────────────────────────────────────────────────


async def get(store: "BaseStore", user_id: str, lesson_id: str) -> Lesson | None:
    item = await store.aget(_namespace(user_id), lesson_id)
    if item is None:
        return None
    return Lesson.model_validate(item.value)


async def top(store: "BaseStore", user_id: str, n: int = 10) -> list[Lesson]:
    """Return the top n active Lessons by recurrence, descending."""
    items = await store.asearch(_namespace(user_id))
    lessons = [Lesson.model_validate(i.value) for i in items]
    active = [l for l in lessons if l.status == "active"]
    return sorted(active, key=lambda l: l.recurrence, reverse=True)[:n]


# ── Write ─────────────────────────────────────────────────────────────────────


async def create(
    store: "BaseStore",
    user_id: str,
    name: str,
    description: str,
    evidence: LessonEvidence,
) -> Lesson:
    lesson = Lesson(name=name, description=description, evidence=[evidence])
    await store.aput(_namespace(user_id), lesson.lesson_id, lesson.model_dump())
    return lesson


async def reinforce(
    store: "BaseStore",
    user_id: str,
    lesson_id: str,
    evidence: LessonEvidence,
) -> Lesson | None:
    lesson = await get(store, user_id, lesson_id)
    if lesson is None:
        return None
    lesson.recurrence += 1
    lesson.evidence.append(evidence)
    lesson.updated_at = _now()
    await store.aput(_namespace(user_id), lesson_id, lesson.model_dump())
    return lesson


async def rename(
    store: "BaseStore",
    user_id: str,
    lesson_id: str,
    new_name: str,
) -> Lesson | None:
    lesson = await get(store, user_id, lesson_id)
    if lesson is None:
        return None
    lesson.name = new_name
    lesson.updated_at = _now()
    await store.aput(_namespace(user_id), lesson_id, lesson.model_dump())
    return lesson


async def retire(
    store: "BaseStore",
    user_id: str,
    lesson_id: str,
) -> Lesson | None:
    lesson = await get(store, user_id, lesson_id)
    if lesson is None:
        return None
    lesson.status = "retired"
    lesson.updated_at = _now()
    await store.aput(_namespace(user_id), lesson_id, lesson.model_dump())
    return lesson


async def merge(
    store: "BaseStore",
    user_id: str,
    lesson_ids: list[str],
    new_name: str,
    new_description: str,
) -> Lesson:
    """Merge multiple lessons into one, summing recurrences and combining evidence."""
    sources = [await get(store, user_id, lid) for lid in lesson_ids]
    sources = [s for s in sources if s is not None]

    combined_recurrence = sum(s.recurrence for s in sources)
    combined_evidence = [e for s in sources for e in s.evidence]

    new_lesson = Lesson(
        name=new_name,
        description=new_description,
        recurrence=combined_recurrence,
        evidence=combined_evidence,
    )
    await store.aput(_namespace(user_id), new_lesson.lesson_id, new_lesson.model_dump())

    # Retire the source lessons
    for lid in lesson_ids:
        await retire(store, user_id, lid)

    return new_lesson


# ── Apply ops from distill node ───────────────────────────────────────────────


async def apply_ops(
    store: "BaseStore",
    user_id: str,
    ops: list[dict],
) -> None:
    """Apply a list of lesson operation dicts produced by the `distill` LLM node.

    Malformed ops are skipped and logged — they never crash the distillation run.
    """
    for op in ops:
        try:
            op_type = op.get("op")
            if op_type == "reinforce":
                await reinforce(
                    store, user_id, op["lesson_id"],
                    LessonEvidence(**op["evidence"]),
                )
            elif op_type == "create":
                await create(
                    store, user_id, op["name"], op["description"],
                    LessonEvidence(**op["evidence"]),
                )
            elif op_type == "merge":
                await merge(
                    store, user_id, op["lesson_ids"],
                    op["new_name"], op["new_description"],
                )
            elif op_type == "rename":
                await rename(store, user_id, op["lesson_id"], op["new_name"])
            elif op_type == "retire":
                await retire(store, user_id, op["lesson_id"])
            else:
                print(f"[lessons] Unknown op type '{op_type}', skipping")
        except Exception as exc:
            print(f"[lessons] Malformed op {op!r}: {exc}")
