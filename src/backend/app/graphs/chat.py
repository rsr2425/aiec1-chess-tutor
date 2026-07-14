"""Chat subgraph — single tool-calling agent.

Game context (pgn, game_summary, user_id, student_rating) is passed in
config.configurable on every turn so the coach always has the full picture.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.config import get_store
from langgraph.prebuilt import create_react_agent

from app import lessons as lessons_store
from app.prompts import chat_system_prompt
from app.schemas import Lesson, TutorReply
from app.tools import make_tools

_CHAT_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-4.1-mini")
_AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "")
_AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL", "")


async def _prompt_fn(state: dict, config: RunnableConfig) -> list[AnyMessage]:
    """Build a fresh system prompt on every turn from config.configurable.

    create_react_agent invokes the prompt with the full agent state dict,
    so the conversation lives under state["messages"]. The student's top-10
    Lessons come from the cross-thread Store (TDD D4 — injected every turn,
    never a tool call).
    """
    cfg = config.get("configurable", {})
    user_id = cfg.get("user_id", "")

    lessons: list[Lesson] = []
    if user_id:
        try:
            store = get_store()
            lessons = await lessons_store.top(store, user_id, n=10)
        except Exception:
            pass  # store unavailable (e.g. bare unit test) — coach without lessons

    system_text = chat_system_prompt(
        lessons=lessons,
        game_summary=cfg.get("game_summary", ""),
        pgn=cfg.get("pgn", ""),
    )
    return [SystemMessage(content=system_text)] + list(state["messages"])


def _llm() -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": _CHAT_MODEL,
        "api_key": _AI_GATEWAY_API_KEY,
        "temperature": 0.3,
    }
    if _AI_GATEWAY_BASE_URL:
        kwargs["base_url"] = _AI_GATEWAY_BASE_URL + "/v1"
    return ChatOpenAI(**kwargs)


graph = create_react_agent(
    model=_llm(),
    tools=make_tools(),
    prompt=RunnableLambda(_prompt_fn),
    response_format=TutorReply,
)
