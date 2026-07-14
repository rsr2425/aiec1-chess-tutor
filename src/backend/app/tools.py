"""The five chat tools injected into the chat agent.

user_id and student_rating are read from config.configurable at execution time —
the LLM never supplies them, and they don't appear in tool signatures.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from app import engine_client
from app import retrieval


def make_tools() -> list:
    """Construct agent tools. Context values come from RunnableConfig at call time."""

    @tool
    async def analyze_position(fen: str, config: RunnableConfig) -> dict:
        """Get Stockfish evaluation for a chess position.

        Args:
            fen: FEN string of the position to analyze.

        Returns eval_cp, best_move_san, best_line_san. Every concrete evaluation
        claim in your reply MUST come from this tool — never invent numbers.
        """
        cfg = config.get("configurable", {})
        rating = cfg.get("student_rating", 1400)
        return await engine_client.analyze_position(fen, student_rating=rating)

    @tool
    def search_moments(query: str, config: RunnableConfig) -> list[dict]:
        """Search the student's past game positions for similar patterns.

        Args:
            query: Natural language description of the position or pattern.
        """
        user_id = config.get("configurable", {}).get("user_id", "")
        retriever = retrieval.moments_retriever(user_id, k=4)
        docs = retriever.invoke(query)
        return [{"content": d.page_content, "metadata": d.metadata} for d in docs]

    @tool
    def search_games(query: str, config: RunnableConfig) -> list[dict]:
        """Search the student's past game summaries.

        Args:
            query: Natural language query about past games.
        """
        user_id = config.get("configurable", {}).get("user_id", "")
        retriever = retrieval.game_summaries_retriever(user_id, k=3)
        docs = retriever.invoke(query)
        return [{"content": d.page_content, "metadata": d.metadata} for d in docs]

    @tool
    def search_library(query: str) -> list[dict]:
        """Search the instructional chess library (Capablanca, Lasker, et al.).

        Args:
            query: Natural language query about a chess concept or principle.
        """
        retriever = retrieval.library_retriever(k=4)
        docs = retriever.invoke(query)
        return [
            {
                "content": d.page_content,
                "book": d.metadata.get("book", ""),
                "author": d.metadata.get("author", ""),
                "section": d.metadata.get("section_title", ""),
                "license": d.metadata.get("license", "public domain"),
            }
            for d in docs
        ]

    web_search = TavilySearch(max_results=3)
    web_search.name = "web_search"
    web_search.description = (
        "Search the web for modern chess content: recent articles, opening theory, "
        "GM game databases, or anything not covered by the library."
    )

    return [analyze_position, search_moments, search_games, search_library, web_search]
