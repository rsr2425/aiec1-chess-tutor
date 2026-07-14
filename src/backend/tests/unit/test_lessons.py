"""Unit tests for lessons.py — in-memory LangGraph Store."""

import pytest
from langgraph.store.memory import InMemoryStore

from app import lessons as lesson_store
from app.schemas import Lesson, LessonEvidence

pytestmark = pytest.mark.asyncio


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def evidence() -> LessonEvidence:
    return LessonEvidence(game_id="game-1", ply=12)


class TestCreate:
    async def test_creates_lesson(self, store, evidence):
        lesson = await lesson_store.create(
            store, "user1", "Trade to simplify", "Trades pieces when already worse.", evidence
        )
        assert lesson.lesson_id
        assert lesson.name == "Trade to simplify"
        assert lesson.recurrence == 1
        assert lesson.status == "active"
        assert lesson.evidence == [evidence]

    async def test_lesson_retrievable(self, store, evidence):
        lesson = await lesson_store.create(store, "user1", "Test", "desc", evidence)
        fetched = await lesson_store.get(store, "user1", lesson.lesson_id)
        assert fetched is not None
        assert fetched.lesson_id == lesson.lesson_id


class TestReinforce:
    async def test_increments_recurrence(self, store, evidence):
        lesson = await lesson_store.create(store, "user1", "Test", "desc", evidence)
        new_evidence = LessonEvidence(game_id="game-2", ply=8)
        updated = await lesson_store.reinforce(store, "user1", lesson.lesson_id, new_evidence)
        assert updated.recurrence == 2
        assert len(updated.evidence) == 2

    async def test_returns_none_for_missing_lesson(self, store, evidence):
        result = await lesson_store.reinforce(store, "user1", "nonexistent", evidence)
        assert result is None


class TestRetire:
    async def test_sets_status_retired(self, store, evidence):
        lesson = await lesson_store.create(store, "user1", "Test", "desc", evidence)
        retired = await lesson_store.retire(store, "user1", lesson.lesson_id)
        assert retired.status == "retired"

    async def test_retired_lesson_excluded_from_top(self, store, evidence):
        lesson = await lesson_store.create(store, "user1", "Test", "desc", evidence)
        await lesson_store.retire(store, "user1", lesson.lesson_id)
        top = await lesson_store.top(store, "user1", n=10)
        assert all(l.lesson_id != lesson.lesson_id for l in top)


class TestMerge:
    async def test_creates_merged_lesson(self, store, evidence):
        l1 = await lesson_store.create(store, "user1", "Lesson A", "desc a", evidence)
        ev2 = LessonEvidence(game_id="game-2", ply=5)
        l2 = await lesson_store.create(store, "user1", "Lesson B", "desc b", ev2)
        # Reinforce l1 to give it recurrence 2
        await lesson_store.reinforce(store, "user1", l1.lesson_id, ev2)

        merged = await lesson_store.merge(
            store, "user1", [l1.lesson_id, l2.lesson_id],
            "Merged Lesson", "Combined description"
        )
        # recurrence = 2 (l1) + 1 (l2) = 3
        assert merged.recurrence == 3
        assert merged.name == "Merged Lesson"

    async def test_source_lessons_retired_after_merge(self, store, evidence):
        l1 = await lesson_store.create(store, "user1", "A", "a", evidence)
        l2 = await lesson_store.create(store, "user1", "B", "b", evidence)
        await lesson_store.merge(store, "user1", [l1.lesson_id, l2.lesson_id], "C", "c")
        assert (await lesson_store.get(store, "user1", l1.lesson_id)).status == "retired"
        assert (await lesson_store.get(store, "user1", l2.lesson_id)).status == "retired"


class TestTop:
    async def test_sorts_by_recurrence_descending(self, store, evidence):
        l1 = await lesson_store.create(store, "user1", "Low", "desc", evidence)
        l2 = await lesson_store.create(store, "user1", "High", "desc", evidence)
        # Reinforce l2 twice
        ev2 = LessonEvidence(game_id="g2", ply=1)
        ev3 = LessonEvidence(game_id="g3", ply=1)
        await lesson_store.reinforce(store, "user1", l2.lesson_id, ev2)
        await lesson_store.reinforce(store, "user1", l2.lesson_id, ev3)

        top = await lesson_store.top(store, "user1", n=10)
        assert top[0].lesson_id == l2.lesson_id
        assert top[0].recurrence == 3

    async def test_respects_n_limit(self, store, evidence):
        for i in range(5):
            await lesson_store.create(store, "user1", f"Lesson {i}", "desc", evidence)
        top = await lesson_store.top(store, "user1", n=3)
        assert len(top) <= 3

    async def test_excludes_retired(self, store, evidence):
        active = await lesson_store.create(store, "user1", "Active", "desc", evidence)
        retired = await lesson_store.create(store, "user1", "Retired", "desc", evidence)
        await lesson_store.retire(store, "user1", retired.lesson_id)
        top = await lesson_store.top(store, "user1", n=10)
        ids = [l.lesson_id for l in top]
        assert active.lesson_id in ids
        assert retired.lesson_id not in ids


class TestApplyOps:
    async def test_apply_create_op(self, store):
        ops = [{
            "op": "create",
            "name": "Test habit",
            "description": "Student does X",
            "evidence": {"game_id": "g1", "ply": 5},
        }]
        await lesson_store.apply_ops(store, "user1", ops)
        top = await lesson_store.top(store, "user1")
        assert len(top) == 1
        assert top[0].name == "Test habit"

    async def test_malformed_op_skipped(self, store):
        ops = [{"op": "create", "name": "Missing fields"}]  # no description or evidence
        # Should not raise — malformed ops are logged and skipped
        await lesson_store.apply_ops(store, "user1", ops)

    async def test_unknown_op_skipped(self, store):
        ops = [{"op": "unknown_op", "some": "data"}]
        await lesson_store.apply_ops(store, "user1", ops)
