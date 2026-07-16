# Blunderstanding — Chess Tutor Agent

> Certification Challenge submission · AI Engineering Certification v1.0

A web-based chess coach that reads your annotated games, identifies your
recurring mistakes, and remembers them across every game you've ever uploaded —
like a real coach's notebook.

**Live demo:** https://blunderstanding.vercel.app  
**Loom walkthrough:** _link after recording_

---

## Certification Task Answers

### Task 1 — Problem & Audience

Adult chess improvers, especially early intermediate players, need personalized feedback after each game to increase their skills.

The audience I'm targetting for this problem is early/intermediate Adult chess improvers. Adults who play chess as a hobby and strive to get better because of the feeling of satisfaction from getting better. Unlike a lot of hobbies, you can literaly see this concretely from a number called an elo rating which tells you how you stack against other players. Since the pandemic, and the release of the widely popular Queen's gambit series, there's been a massive spike in popularity. I've personally seen decently sized communities online of adult improvers, who spend lots of practicing and are even willing to spend money to buy courses (e.g. chessable) and fly to tournaments. 

**How the user solves this today:**

![Task 1 — how an adult improver reviews games today](graphs/task1_user_workflow.png)

There's a lot of generic resources online, but personalized feedback is ideal. Chess.com for example has a game review option, but it's really hard for someone who's not very skilled to understand the results, because the review relies on a game engine. And engines are A LOT better than humans now and don't play in very "human" ways. So a "mistake" might not actually be a mistake practically speaking for a hobbyist. As mentioned before, adults may be willing to pay money and invest the time, but not necessarily for coaching. Coaching can be expensive, especially for a side hobby (if you start as an adult, you're very very VERY unlikely to become a pro lol). It can also be hard to coordinate schedules.

**Questions users will ask (example input → output pairs):**

| User input | Expected output |
|---|---|
| *Uploads an annotated PGN of a lost game* | 2–3 takeaways tied to specific moments in that game, at the student's level — not raw engine lines |
| "What was my biggest mistake?" | The single highest-impact moment, explained in terms of the student's own reasoning (from their annotations), with the position shown on the board |
| "Why was 14...Nxe5 actually bad? I thought I was winning a pawn." | An explanation grounded in the engine's verdict but framed around the student's misconception (e.g. counting attackers but not defenders) |
| "Have I made this kind of mistake before?" | Retrieved similar moments from the student's past games, with the recurring pattern named |
| "What should I study next?" | A recommendation driven by the student's persistent Lessons (their most recurrent weaknesses), not generic advice |
| "What does Capablanca say about doubled pawns?" | A grounded answer citing the ingested classics (library RAG), not a hallucinated quote |

Output quality is evaluated two ways (Task 5): retrieval quality with Ragas (faithfulness, answer relevancy, context precision/recall) over a 42-question test set on the library corpus, and coaching quality with a planted-mistake benchmark — synthetic student annotations with known misconceptions are injected into real games, and we measure whether the generated takeaways actually catch them (precision/recall + an LLM-as-judge coaching rubric).

### Task 2 — Solution

An agentic chess tutor for adult improvers: you upload a game (ideally with your own comments), it finds the moments that actually decided the game, explains them at your level, and — the differentiator — keeps a persistent "coach's notebook" of your recurring mistakes (Lessons) that grows across every game you upload and shapes every future conversation.

Under the hood there are two cooperating LangGraph graphs. The **distillation graph** runs in the background on upload: it parses the PGN, gets a Stockfish evaluation of every move from a dedicated engine service, selects the handful of decisive moments with deterministic code (so benchmarks are stable), has the LLM describe them and distill takeaways, and updates the student's Lessons and the vector store. The **chat agent** is a ReAct agent that gets the student's top-10 Lessons, the game summary, and the PGN injected into its system prompt every turn, and can call five tools (engine analysis, the student's own past moments and games, the classics library, and web search). Replies are structured — position references come back as FENs the UI renders as clickable board chips.

**Infrastructure:**

![Task 2 — deployed infrastructure](graphs/task2_infrastructure.png)

**Agent workflow (distillation graph + chat agent):**

![Task 2 — agent workflow](graphs/task2_agent_workflow.png)

1. **LLM(s)** — `openai/gpt-4.1-mini` for both chat and distillation, served through the **Vercel AI Gateway** (OpenAI-compatible), so swapping models is a one-env-var change (`CHAT_MODEL` / `DISTILL_MODEL` — this is exactly how the Task 6 model swap works).
2. **Agent orchestration framework** — **LangGraph**: a linear `StateGraph` for distillation and `create_react_agent` for chat, both served by the LangGraph Agent Server (locally in Docker, in prod on LangSmith).
3. **Tool(s)** — `analyze_position` (Stockfish via the engine service), `search_moments` and `search_games` (the student's own history, user-filtered), `search_library` (chess classics RAG), and `web_search` (**Tavily**, the external API).
4. **Embedding model** — `text-embedding-3-small`, also through the AI Gateway.
5. **Vector Database** — **Qdrant** (Qdrant Cloud in prod, container locally) with three collections: `library`, `moments`, `game_summaries`.
6. **Monitoring tool** — **LangSmith** tracing on the deployment: every LLM call, tool call, and graph node execution is traced.
7. **Evaluation framework** — **Ragas** for retrieval metrics plus a custom planted-mistake benchmark with an LLM-as-judge rubric (`evals/`).
8. **User interface** — **Next.js** + Tailwind + `react-chessboard`, responsive (works on a phone), streaming chat over SSE.
9. **Deployment** — **Vercel** (UI), **LangSmith Deployment** (agent), **Render** (engine service), **Qdrant Cloud** (vectors).
10. **Memory** — the **LangGraph Store** holds each student's persistent Lessons across threads and sessions (written by distillation, injected into every chat turn); thread-level conversation memory comes from the LangGraph checkpointer. One honest caveat: Maia-2 (human-move-probability model) is designed into the engine service but effectively disabled — the system runs Stockfish-only, with Maia fields nullable end-to-end.

### Task 3 — Data

| Collection | Content | Chunking strategy |
|---|---|---|
| `library` | Public-domain classics (Capablanca, Lasker) via Gutenberg | Book's own section headings; long sections split with RecursiveCharacterTextSplitter(1000/100) |
| `moments` | Key positions from the Student's games | One Moment = one position + LLM-written description paragraph |
| `game_summaries` | Per-game summary paragraphs | One row per game |

**External API:** Tavily web search (`web_search` tool in the chat agent).

### Task 4 — Prototype

- **UI (public entry point):** https://blunderstanding.vercel.app
- **Agent:** LangSmith deployment https://chess-tutor-e7b2caed588f50fcaace1374635bf330.us.langgraph.app (API-key protected; called server-side by the UI's API routes)
- **Engine Service:** Render https://chess-engine-server-hbp2.onrender.com (bearer-token protected; `/healthz` is public)
- **Vector store:** Qdrant Cloud (`library` corpus ingested: 419 chunks)

### Task 5 — Evaluations

Two harnesses, both in `evals/` with committed result tables in `evals/results/`.

**5.1 Retrieval (Ragas).** Test set: 42 questions over the `library` corpus —
12 hand-written golden questions grounded in the two ingested books + 30
synthetic questions generated from random corpus chunks, cached in
`evals/testset.jsonl` so every run scores identical questions. Baseline
(dense-only) results:

| Metric | Baseline (dense) |
|---|---|
| faithfulness | 0.884 |
| answer_relevancy | 0.788 |
| context_precision | 0.741 |
| context_recall | **0.595** |

**Conclusion:** generation is faithful to what gets retrieved, but dense-only
retrieval *misses* relevant sections — context recall is the weak link (0.60).
That is what the Task 6 advanced retriever targets.

**5.2 Planted-mistake benchmark.** 20 CC0 lichess games (rapid, both players
<1500). An LLM plants 2–3 known misconceptions from an 8-entry catalog as
synthetic student annotations (annotator model fixed, annotations cached, so
every run distills identical inputs). The real distillation graph runs per
game; a separate judge model (`gpt-4.1`) scores whether takeaways catch the
planted misconceptions (precision/recall) plus a 0–3 coaching-quality rubric.
Results table in `evals/results/planted_mistakes_*.md`.

### Task 6 — Advanced Retriever + Improvement

1. **Advanced retriever:** BM25 + dense `EnsembleRetriever` (equal weights) on
   `library`. Rationale: chess vocabulary ("Caro-Kann", "skewer", "f7") is
   exact-match-sensitive; pure semantic search blurs it. Implemented in
   production (`src/backend/app/retrieval.py`, enabled with
   `USE_ENSEMBLE_RETRIEVER=true`) and evaluated on the same cached 42-question
   testset:

   | Metric | Baseline (dense) | Ensemble (BM25+dense) | Δ |
   |---|---|---|---|
   | faithfulness | 0.884 | 0.876 | −0.008 |
   | answer_relevancy | 0.788 | 0.863 | **+0.075** |
   | context_precision | 0.741 | 0.716 | −0.025 |
   | context_recall | 0.595 | 0.833 | **+0.238** |

   **Conclusion:** the ensemble fixes exactly the weakness the baseline showed —
   recall of relevant sections jumps 24 points (0.60 → 0.83) and answers get
   more relevant, at a negligible cost to precision/faithfulness. Adopted.

2. **Model swap:** `DISTILL_MODEL` env var changed from `openai/gpt-4.1-mini`
   to `openai/gpt-4.1` through the gateway (a one-variable change thanks to the
   AI Gateway). Scored on the identical cached benchmark inputs; before/after
   precision/recall table in `evals/results/`.

### Task 7 — Next Steps

See `PRD.md §7`:
- Puzzle curriculum from CC0 lichess puzzle DB matched to Lessons
- Maia-3 / rating-adaptive feedback depth
- Chessformer position-native embeddings replacing describe-then-embed
- Real authentication + chess.com/lichess account sync
- Interactive board play

---

## Local Development

```bash
cp .env.example .env
# fill in API keys

make build         # first run (builds images)
make up            # subsequent runs

# localhost:3001   — UI
# localhost:8000   — LangGraph backend
# localhost:8001   — Engine service
# localhost:6333   — Qdrant

# Run unit tests (no Docker needed):
make test-unit
make test-engine

# Run integration tests (requires Docker):
make test-integration

# Ingest library corpus into Qdrant:
make ingest
```

## Repo Layout

```
chess-tutor/
├── src/
│   ├── frontend/           # Next.js → Vercel
│   ├── backend/            # LangGraph agent → LangSmith
│   └── chess-engine-server/# FastAPI + Stockfish/Maia-2 → Render
├── scripts/                # ingestion + benchmark data fetch
├── evals/                  # evaluation harness
├── docs/adr/               # architecture decision records
├── docker-compose.yml      # local dev
└── docker-compose.test.yml # integration tests
```
