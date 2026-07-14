"""Planted-mistake benchmark — Task 5.2 / 6.2.

Pipeline:
  1. Load PGNs from evals/planted_mistakes/games/ (fetched by fetch_lichess_games.py)
  2. Engine-pass each game to find real mistakes
  3. LLM writes synthetic student annotations embedding cataloged misconceptions
  4. Run the real distillation graph per game (fresh benchmark user_id)
  5. Score Takeaway precision/recall vs planted misconceptions + coaching rubric

Results → evals/results/planted_mistakes_{model}_{ts}.md
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

GAMES_DIR = Path(__file__).parent / "games"
RESULTS_DIR = Path(__file__).parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "")
AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL", "")
DISTILL_MODEL = os.getenv("DISTILL_MODEL", "openai/gpt-4.1-mini")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai/gpt-4.1")  # different from generation model

MISCONCEPTION_CATALOG = [
    "Trades pieces to simplify while already in a worse position",
    "Counts attackers without counting defenders",
    "Grabs material while ignoring king safety",
    "Assumes a threat is serious without verifying it works",
    "Moves the queen early and loses tempo to attacks",
    "Neglects development in favour of pawn grabbing",
    "Overlooks that a piece is pinned when calculating tactics",
    "Fails to consider the opponent's best response",
]


def _llm(model: str = None):
    from langchain_openai import ChatOpenAI
    m = model or DISTILL_MODEL
    kwargs = {"model": m, "api_key": AI_GATEWAY_API_KEY, "temperature": 0.3}
    if AI_GATEWAY_BASE_URL:
        kwargs["base_url"] = AI_GATEWAY_BASE_URL + "/v1"
    return ChatOpenAI(**kwargs)


async def annotate_game_synthetically(pgn: str, planted: list[str]) -> str:
    """Have an LLM write student annotations embedding the planted misconceptions."""
    llm = _llm()
    prompt = (
        f"You are writing synthetic student annotations for a chess game to create a benchmark.\n"
        f"The student has these misconceptions (embed 2-3 of them naturally as comments at "
        f"the moves where mistakes occur):\n"
        + "\n".join(f"- {m}" for m in planted)
        + f"\n\nOriginal PGN (no comments):\n{pgn}\n\n"
        "Return the PGN with your synthetic student comments added at blunder moves. "
        "Keep it realistic — the student sounds earnest and explains their thinking, "
        "but their reasoning reflects the listed misconceptions."
    )
    response = await llm.ainvoke(prompt)
    return response.content


async def judge_takeaway(takeaway: str, planted: list[str]) -> dict:
    """LLM-as-judge: does this takeaway address a planted misconception?"""
    llm = _llm(JUDGE_MODEL)
    prompt = (
        f"Planted misconceptions:\n" + "\n".join(f"- {m}" for m in planted) + "\n\n"
        f"Takeaway to evaluate: {takeaway}\n\n"
        "Does this takeaway address one of the planted misconceptions? "
        "Also rate on 0-3 scale: (0) generic/vague, (1) specific to position, "
        "(2) specific + actionable, (3) specific + actionable + position-grounded.\n"
        'Respond as JSON: {"matches_misconception": true/false, "matched": "...", "rubric": 0-3}'
    )
    response = await llm.ainvoke(prompt)
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {"matches_misconception": False, "matched": None, "rubric": 0}


async def run_benchmark() -> None:
    pgn_files = sorted(GAMES_DIR.glob("*.pgn"))
    if not pgn_files:
        print(f"No PGN files found in {GAMES_DIR}. Run scripts/fetch_lichess_games.py first.")
        return

    print(f"Running benchmark on {len(pgn_files)} games …")

    results = []
    for pgn_path in pgn_files[:5]:  # limit for quick runs; remove cap for full benchmark
        pgn = pgn_path.read_text()
        # Pick 2-3 random misconceptions to plant
        import random
        planted = random.sample(MISCONCEPTION_CATALOG, k=2)

        print(f"\n{pgn_path.name} — planting: {planted}")
        annotated_pgn = await annotate_game_synthetically(pgn, planted)

        # Run distillation graph
        from app.graphs.distillation import graph as distillation_graph
        from uuid import uuid4
        state = await distillation_graph.ainvoke({
            "user_id": f"benchmark-{uuid4().hex[:8]}",
            "game_id": pgn_path.stem,
            "pgn": annotated_pgn,
            "student_color": "white",
            "student_rating": 1400,
        })

        takeaways = state.get("takeaways", [])
        judgments = []
        for t in takeaways:
            j = await judge_takeaway(t.text if hasattr(t, "text") else t["text"], planted)
            judgments.append(j)

        matched = sum(1 for j in judgments if j["matches_misconception"])
        rubric_avg = sum(j["rubric"] for j in judgments) / max(len(judgments), 1)

        results.append({
            "game": pgn_path.name,
            "planted_count": len(planted),
            "takeaway_count": len(takeaways),
            "matched": matched,
            "precision": matched / max(len(takeaways), 1),
            "recall": matched / len(planted),
            "rubric_avg": rubric_avg,
        })
        print(f"  precision={results[-1]['precision']:.2f}, recall={results[-1]['recall']:.2f}, rubric={rubric_avg:.1f}")

    # Write results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"planted_mistakes_{DISTILL_MODEL.replace('/', '_')}_{ts}.md"

    lines = [
        f"# Planted-Mistake Benchmark — {DISTILL_MODEL} — {ts}\n",
        "| Game | Planted | Takeaways | Matched | Precision | Recall | Rubric (avg) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['game']} | {r['planted_count']} | {r['takeaway_count']} | "
            f"{r['matched']} | {r['precision']:.2f} | {r['recall']:.2f} | {r['rubric_avg']:.1f} |"
        )

    avg_p = sum(r["precision"] for r in results) / max(len(results), 1)
    avg_r = sum(r["recall"] for r in results) / max(len(results), 1)
    avg_rub = sum(r["rubric_avg"] for r in results) / max(len(results), 1)
    lines += [
        "",
        f"**Avg precision: {avg_p:.2f} | Avg recall: {avg_r:.2f} | Avg rubric: {avg_rub:.1f}**",
    ]

    out_path.write_text("\n".join(lines))
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
