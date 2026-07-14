# PRD — Chess Tutor Agent

**Status:** Agreed plan of record (grilling session, 2026-07-08)
**Deadline:** Certification Challenge submission due **Tuesday, July 14, 2026**
**Companion docs:** [`CONTEXT.md`](CONTEXT.md) (ubiquitous language — terms capitalized below are defined there), [`docs/adr/`](docs/adr/) (decision records), [`00_Docs/Certification Challenge/README.md`](<00_Docs/Certification Challenge/README.md>) (requirements)

---

## 1. Problem

Adult chess improvers (under ~1500 chess.com rating) who can't afford or don't
want a human coach cannot tell which of their recurring mistakes actually
matter, so they keep making them.

Today they review games with engine analysis (Stockfish, chess.com Game
Review). The engine gives precise objective truth about *moves* but says
nothing about the player's *reasoning*, never remembers previous games, and
never connects this game's blunder to the same habit from last month. Truth
without teaching.

**Audience:** the Student — an adult improver willing to invest real effort,
including writing their own thoughts into their PGNs. Motivated enough to
annotate; not served by generic engine output.

## 2. Solution (one sentence)

A web-based chess tutor agent that reads the Student's annotated games,
compares their stated reasoning against engine-grounded reality, distills 2–3
Takeaways per game, and — like a real coach — maintains a persistent,
curated picture of the Student's recurring weaknesses across every game
they've ever uploaded.

**Differentiator:** nobody else coaches the *thought process*. Engines see
moves; this tutor sees the Annotation ("I traded queens to simplify") next to
the truth (the trade lost a pawn) next to the history (third game running
with the same trade-off misjudgment).

## 3. Core user flow

1. **Identify** — lightweight identity: enter a username, no password. The
   username keys all persistence. (Real auth: post-POC.)
2. **Upload** — an Annotated Game (PGN with the Student's thoughts as
   comments). Bare Games accepted in degraded moves-only mode; the Annotated
   Game is the designed-for input.
3. **Distillation** (automatic, on upload):
   - Parse PGN; run the engine over every position; flag the largest
     eval-swing mistakes.
   - Select key Moments; write a descriptive paragraph per Moment; embed and
     index Moments and a Game Summary.
   - Distill **2–3 Takeaways** grounded in this game *and* the Student's
     existing Lessons.
   - Curate the Lesson list like a coach's notebook: each Takeaway either
     reinforces an existing Lesson (Recurrence +1) or founds a new one; the
     agent may merge, rename, or retire Lessons. Lessons are pitched at the
     level of a *correctable habit* — not a topic, not a single position.
     Top ~10 Lessons by Recurrence = the tutor's working picture.
4. **Review chat** — the Student discusses the game with the agent. A
   read-only board panel renders any position the tutor references (agent
   returns FEN in a structured field) and lets the Student step through the
   game. No interactive play on the board (post-POC).

## 4. Architecture

### Agent (LangGraph — one system, two subgraphs)

| Subgraph | Nature | Contents |
|---|---|---|
| **Distillation** | Deterministic pipeline, LLM nodes inside fixed edges | parse → engine pass → Moment selection → Takeaway distillation + Lesson curation → indexing |
| **Chat** | Single tool-calling agent | five tools below |

**Chat tools:**
1. **Engine** (via Engine Service): Maia-2 human-realistic analysis; Stockfish objective eval
2. **Moments search** (Qdrant)
3. **Game Summaries search** (Qdrant)
4. **Library search** (Qdrant) — cite instructional classics to the Student
5. **Tavily web search** — live/modern chess content (satisfies external-API requirement)

No multi-agent. Five tools on one agent; multi-agent adds debugging surface
without rubric benefit.

### Engines

- **Maia-2 first** (`pip install maia2`, CPU inference): rating-conditioned
  human move probabilities + win probability → "would a player at your level
  find this? how alarming is this *at 1400*?"
- **Stockfish** (python-chess): objective ground truth for concrete claims
  ("this loses a pawn"). Fallback if Maia-2 fights us — dropping Maia is
  deleting an endpoint, not re-architecting.
- Every concrete chess claim the tutor makes must be engine-grounded. The
  LLM decides *what to teach*; the engine decides *what is true*.

### Data stores

| Store | Contents | Unit |
|---|---|---|
| Qdrant `library` | Public-domain classics (Gutenberg: Capablanca, Lasker, et al.), optional Wikibooks (CC BY-SA, attributed). **Not lichess articles — no public license (ADR 0001).** | book section chunk |
| Qdrant `moments` | Key positions from the Student's games: FEN + move + Annotation + engine verdict, embedded via a written descriptive paragraph | one Moment |
| Qdrant `game_summaries` | One paragraph per uploaded game: opening, story, result, Takeaways | one game |
| LangGraph checkpointer | Conversation memory (per thread) | — |
| LangGraph cross-thread Store | **Lessons**, keyed by user id (the required memory component, layer 2) | one Lesson |

The describe-then-embed paragraph is a deliberate text proxy for position
embeddings; the long-term upgrade path is chessformer-style position-native
vectors — same store semantics, different encoder.

### Models & gateway

- **Vercel AI Gateway** (hard requirement; proven in course session 06)
- Chat + distillation: `openai/gpt-5.4-mini` (default; swappable via gateway)
- Embeddings: `text-embedding-3-small`
- Fireworks: back-pocket second provider; not load-bearing

### Deployment (ADR 0002)

| Service | Where | Notes |
|---|---|---|
| LangGraph agent | **LangSmith** | course session 09 shape; torch-free image |
| Next.js chat UI + board | **Vercel** | passthrough proxy; `react-chessboard` + `chess.js`; responsive (board stacks above chat on mobile) |
| Engine Service (Maia-2 + Stockfish) | **Render, CPU** | barebones FastAPI `/analyze` endpoints; no GPU (23M params, dozens of positions per upload) |

**Monitoring:** LangSmith tracing.

## 5. Evaluation (Task 5)

Two-part harness:

1. **Retrieval eval** — Ragas over Library + Moments with a synthetic test
   set (course sessions 05/06 pattern): faithfulness, context
   precision/recall, answer relevancy. Referee for Task 6's retriever table.
2. **Planted-mistake benchmark** (distillation quality) — ~15–20 real
   sub-1500 games from the CC0 lichess database; engine identifies actual
   mistakes; an LLM writes synthetic student annotations embedding cataloged
   misconceptions. Metric: Takeaway precision/recall against planted
   misconceptions + LLM-as-judge coaching rubric (specific, actionable,
   position-grounded). The user's own real annotated games anchor the demo
   and sanity-check the synthetic annotations.

## 6. Task 6 improvements (pre-committed, harness-refereed)

1. **Advanced retriever:** hybrid BM25 + dense ensemble (chess vocabulary —
   "Caro-Kann", "f7", "skewer" — is exact-match-sensitive; pure semantic
   search blurs it). Cohere rerank stacks on top if needed (session 07 code).
2. **Other component:** distillation model swap through the gateway
   (`gpt-5.4-mini` → stronger model), before/after on the planted-mistake
   benchmark.

## 7. Out of scope (POC) → Task 7 next steps

- Puzzles (CC0 lichess puzzle DB, 6M tagged — match puzzles to Lessons)
- Maia-3 / rating-adaptive feedback depth
- Chessformer position-native embeddings replacing describe-then-embed
- Real authentication
- chess.com / lichess account sync (auto-import games via public APIs)
- Interactive board play; hand-picked puzzle curricula; thought-process drills

## 8. Certification task mapping

| Cert task | Covered by |
|---|---|
| 1 — Problem/audience | §1; golden eval questions come from §5 benchmark design |
| 2 — Solution + diagrams | §2–4 (infra diagram: gateway ✓, memory ✓, browser/phone ✓) |
| 3 — Data | §4 data stores; chunking = Moment/Game Summary as natural units, section chunks for Library; external API = Tavily |
| 4 — Prototype + public deploy | §4 deployment |
| 5 — Evals | §5 |
| 6 — Advanced retriever + improvement | §6 |
| 7 — Next steps | §7 |

## 9. Risks

| Risk | Mitigation |
|---|---|
| Maia-2 deployment friction | Stockfish fallback behind same Engine Service interface; nixing Maia = deleting one endpoint |
| LangSmith deploy cost/limits | Session 09 already walked this path; worst case the agent moves to Render alongside the engine service |
| Lesson granularity drift (one giant "tactics" lesson, or nothing recurs) | Correctable-habit rubric in the distillation prompt; planted-mistake benchmark catches drift |
| Deadline (6 days) | Every component has working course code to crib (sessions 02, 03, 05, 06, 07, 09); Maia and rerank are the only novel integrations, both optional |
