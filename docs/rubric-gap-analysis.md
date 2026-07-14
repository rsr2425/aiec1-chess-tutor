# Rubric Gap Analysis — Chess Tutor / Blunderstanding (Independent Re-verification)

**Generated:** 2026-07-13 (supersedes prior analysis of same date)
**Rubric source:** `00_Docs/Certification Challenge/README.md` (official Tasks 1–7 + Final Submission), cross-referenced with `PRD.md §8` and `TDD.md §15`
**Method:** every claim below was verified by reading the actual files and, where possible, inspecting the live local stack (Docker containers + Qdrant contents). Nothing was carried over from the prior analysis without re-checking.

---

## Executive summary

The **application code is real and substantially works**: all three services are implemented, unit tests pass (pytest caches in both Python projects show all unit tests green at last run), and the live local Qdrant instance contains **62 Moments and 19 Game Summaries** — hard evidence the full distillation pipeline (engine pass → LLM nodes → indexing) has run end-to-end locally ~19 times with real models.

The **submission layer is where the challenge fails today**:

- **The repo has zero git commits and no remote.** `git log` fails with "branch 'main' does not have any commits yet". There is no public GitHub repo — the final submission's most basic requirement.
- **Nothing is deployed.** All URLs in README are placeholders. No Loom.
- **The `library` collection is empty (0 points)** — the RAG corpus was never ingested, so `search_library` returns nothing and the retrieval eval cannot run.
- **No eval was ever executed.** `evals/results/` and `evals/planted_mistakes/games/` contain only `.gitkeep`. Worse, the eval harnesses **cannot run as wired** (missing deps; store-injection crash — details below).
- **README task answers are skeletal** (Task 1 trails off mid-sentence, Task 2 is blank bullets, Tasks 5/6 point at empty directories).

| Cert task | Verdict |
|---|---|
| 1 — Problem & audience | **PARTIAL** |
| 2 — Solution + diagrams + gateway/memory/browser | **PARTIAL** |
| 3 — Data, chunking, external API | **DONE** (write-up + code), with an execution caveat |
| 4 — E2E prototype + public deploy | **PARTIAL** (works locally; zero public deployment) |
| 5 — Test set + harness + conclusions | **MISSING** (harness code exists but is broken/unrunnable; no data, no results) |
| 6 — Advanced retriever + 2nd improvement, tables | **MISSING** (code sketch only; nothing run; no tables) |
| 7 — Next steps | **DONE** |
| Final submission (repo, Loom, written doc) | **MISSING** |

---

## Task-by-task verdicts with evidence

### Task 1 — Problem, Audience, Scope — PARTIAL

| Deliverable | Verdict | Evidence |
|---|---|---|
| 1-sentence problem statement | DONE | `README.md:18` ("Adult chess improvers … need personalized feedback after each game") |
| 1–2 paragraphs on why / who / today / why-not-enough | DONE | `README.md:20-22` — covers audience, current handling (chess.com Game Review), and why engine output fails hobbyists |
| Workflow diagram of how the user solves it today | **MISSING** | No diagram anywhere in `README.md` or `docs/` |
| List of eval questions / input-output pairs | **MISSING** | `README.md:24` literally trails off: `"Output can be evaluated against--------"`. The only questions in the repo are 4 golden questions buried in `evals/retrieval_ragas.py:85-102`, never surfaced as a Task 1 deliverable. TDD §11.1 promised ~12 golden Moments/Summaries questions — none exist. |

### Task 2 — Proposed Solution — PARTIAL

| Deliverable | Verdict | Evidence |
|---|---|---|
| 1-sentence solution | PARTIAL | `README.md:28` has the fragment "A Agentic Chess Tutor for Adult Chess improvers"; the real sentence exists only in `PRD.md §2` |
| Infra diagram + 1 sentence per component (LLM, orchestration, tools, embeddings, vector DB, monitoring, evals, UI, deploy) | **MISSING** | `README.md:30-39` is a checklist with **blank dashes for all 10 items**. No committed diagram (TDD §2's ASCII topology is source material, not a submission answer). |
| Agent workflow diagram + 1–2 paragraphs | **MISSING** | Nothing in README or `docs/` |
| Requirement: LLM gateway | DONE (code) | Vercel AI Gateway wired via `AI_GATEWAY_BASE_URL + "/v1"` in `src/backend/app/graphs/chat.py:43-44`, `distillation.py:54-55`, `retrieval.py:44-45`, both eval scripts |
| Requirement: memory component | **PARTIAL** | Cross-thread Lessons Store is fully implemented for *writes* (`src/backend/app/lessons.py`, called from the `distill` node) and the LangGraph checkpointer gives thread memory. **But the chat agent never reads Lessons**: `src/backend/app/graphs/chat.py:29-33` calls `chat_system_prompt(lessons=[], …)` — hardcoded empty list. The PRD's core differentiator ("persistent coach's picture in every reply", TDD D4) is not functional at chat time. |
| Requirement: runs on phone + laptop in a browser | PARTIAL | Responsive layout exists (`app/coach/page.tsx:100` — `flex-col md:flex-row`), but nothing is publicly reachable, so it cannot actually be run on a phone today |

### Task 3 — Data — DONE (with execution caveat)

| Deliverable | Verdict | Evidence |
|---|---|---|
| Chunking strategy described + justified | DONE | `README.md` Task 3 table; implemented for real in `scripts/ingest_library.py` (section-heading split via `SECTION_RE`, `RecursiveCharacterTextSplitter(1000/100)` for sections > ~1500 tokens, deterministic md5 point IDs) |
| Own data (RAG) + external API + how they interact | DONE | Three Qdrant collections in `src/backend/app/retrieval.py` (user-filtered `moments`/`game_summaries`, shared `library`); Tavily via `langchain_tavily.TavilySearch` in `src/backend/app/tools.py:78-83` |

**Caveat:** the design is implemented, but the `library` collection in the running local Qdrant has **0 points** (verified via `GET /collections/library`: `points_count: 0`). `make ingest` was never run. `search_library` currently retrieves nothing, and the retrieval eval has no corpus to evaluate against.

### Task 4 — End-to-end prototype + public deployment — PARTIAL

**Prototype: DONE locally (verified beyond code-reading).**
- All four containers are up and healthy (`chess-tutor-backend-1`, `chess-engine-server-1`, `qdrant-1`, `frontend-1`).
- Qdrant contains **62 moments and 19 game_summaries** — ~19 real distillation runs completed end-to-end (engine pass, LLM describe/distill/summarize, embedding upserts).
- Engine service: `/analyze/game`, `/analyze/position`, `/healthz` implemented (`src/chess-engine-server/main.py`), correct white/black cp_loss POV handling (`engine/stockfish.py:74-80`), mate → ±10000.
- Frontend: upload → background run → poll → takeaways → chat with SSE streaming and clickable FEN chips → read-only stepper board are all implemented (`app/coach/page.tsx`, `components/UploadCard.tsx`, `Chat.tsx`, `BoardPanel.tsx`, `app/api/upload/route.ts`, `app/api/upload/[runId]/route.ts`, `app/api/chat/route.ts`). Keys stay server-side (`lib/langgraph.ts`).

**Public deployment: MISSING.**
- `README.md:9,53-55`: Live demo, LangSmith, Vercel, Render URLs are all `_link_` placeholders.
- **No git history at all** (zero commits, no remote), so nothing has been pushed anywhere, let alone deployed.
- No Loom recording.

### Task 5 — Evals — MISSING

| Deliverable | Verdict | Evidence |
|---|---|---|
| Test data set | **MISSING** | Retrieval: only **4** golden questions (`evals/retrieval_ragas.py:85-102`) vs. TDD §11.1's ~40 synthetic + ~12 golden; `TestsetGenerator` is imported (line 27) but **never used**. Planted-mistake: `evals/planted_mistakes/games/` contains only `.gitkeep` — zero benchmark games fetched. The 8-entry misconception catalog does exist (`run.py:30-39`). |
| Eval harness | **PARTIAL (code exists, cannot run as wired)** | Two scripts exist with the right shape (Ragas metrics, LLM-as-judge with `JUDGE_MODEL` ≠ generation model, precision/recall, markdown output). But: (a) `ragas`, `datasets`, and `rank_bm25` are **not declared in any pyproject/uv.lock** — `make eval-retrieval` runs the script inside the backend container where the import guard raises `SystemExit`; (b) `evals/planted_mistakes/run.py:107` calls `distillation_graph.ainvoke(...)` directly on the compiled graph — the `distill` node's injected `store` parameter (`distillation.py:195`) is only provided by the LangGraph server, so a direct invoke **crashes at the distill node**; (c) `run.py:95` caps at 5 games (`pgn_files[:5]`) vs. the promised 15–20, and always plants exactly 2 misconceptions (`k=2`, line 99) vs. "2–3". |
| Conclusions about pipeline performance | **MISSING** | `evals/results/` contains only `.gitkeep`; README Task 5 says "See `evals/results/`" — there is nothing there and no numbers or conclusions anywhere. |

### Task 6 — Advanced retriever + second improvement — MISSING

| Deliverable | Verdict | Evidence |
|---|---|---|
| Advanced retrieval implemented + rationale | **PARTIAL** | Rationale write-up exists (`README.md` Task 6: chess vocabulary is exact-match-sensitive). BM25+dense `EnsembleRetriever` code exists **only inside the eval script** behind `--retriever ensemble` (`evals/retrieval_ragas.py:71-77`); the production path in `src/backend/app/retrieval.py:139-148` is a **commented-out stub** — the app itself never uses it. `rank_bm25` (required by `BM25Retriever`) is not a declared dependency anywhere, so even the eval-script path fails at import. |
| Before/after performance table | **MISSING** | No table; nothing was ever run (empty `evals/results/`, empty library collection to retrieve from) |
| Second improvement with harness evidence | **MISSING** | The model swap is wired as a one-env-var change (`DISTILL_MODEL` used in `distillation.py:37` and `run.py:27`) — but no before/after benchmark was ever executed, so there is zero evidence of "meaningfully improved response" |

### Task 7 — Next steps — DONE

`README.md` Task 7 restates PRD §7 (puzzle curriculum, Maia-3, chessformer embeddings, auth + account sync, interactive board). This satisfies the reflective deliverable, though a sentence on "what I'd keep vs. change for Demo Day" would strengthen it.

### Final Submission requirements — MISSING

- Public GitHub repo: **does not exist** — the local repo has no commits and no remote.
- ≤10-min Loom demo: **missing** (placeholder at `README.md:10`).
- Written document addressing each deliverable: **partial** (see Tasks 1, 2, 5, 6 above).
- All relevant code: present locally, but not shared anywhere.

---

## Verified functional bugs and dead code

1. **Lessons never injected into chat** — `src/backend/app/graphs/chat.py:29-33` passes `lessons=[]` unconditionally. `chat_system_prompt` (`prompts.py:68-110`) fully supports a lessons block; it just never receives data. The chat agent also has no store access and no lessons tool, so there is *no* path by which the coach's notebook reaches a conversation. This guts the PRD's differentiator and weakens the Task 2 memory requirement.
2. **Maia-2 integration is almost certainly dead code** — `src/chess-engine-server/engine/maia.py:26` calls `maia2.load()` and line 44 calls `_model.predict(board, rating=…, top_k=…)`. The published `maia2` pip package exposes `maia2.model.from_pretrained(...)` + `maia2.inference.*`; there is no top-level `load()`. Because every call is wrapped in `try/except → None`, Maia silently self-disables in every environment. Graceful degradation to Stockfish-only is designed-in (TDD D9), so nothing crashes — but PRD §4's "Maia-2 first" human-findability feature does not actually exist, and no test would catch it (tests only assert the *disabled* path returns null).
3. **Planted-mistake benchmark crashes by construction** — `evals/planted_mistakes/run.py` invokes the compiled distillation graph directly; the `distill` node's injected `store` is only available under `langgraph dev`/LangSmith deployments. Direct `ainvoke` → `lesson_store.top(None, …)` → AttributeError. The harness has clearly never completed a run.
4. **Eval dependencies undeclared** — `ragas`, `datasets`, `rank_bm25` appear in no `pyproject.toml`/`uv.lock` (checked both Python projects). `Makefile` `eval-retrieval`/`eval-planted` run inside the backend container where these imports fail. (`zstandard` for `fetch_lichess_games.py` *is* in the backend lock.)
5. **Engine integration test has a wrong assertion** — `src/chess-engine-server/tests/integration/test_endpoints.py:32` asserts `len(body["plies"]) == 4` for Scholar's Mate, but the conftest PGN (`tests/conftest.py:14`) is 7 half-moves (1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6 4.Qxf7#). The unit test correctly expects 7. Confirms the moves-vs-plies confusion and that the integration suite has never passed. (Both projects' `.pytest_cache/v/cache/nodeids` list **only unit tests** — integration tests were never executed locally.)
6. **TDD's promised full-graph smoke test doesn't exist** — `src/backend/tests/integration/test_distillation_graph.py` defines `FAKE_DISTILL_JSON`/`FAKE_SUMMARY` and imports `FakeListChatModel`, but only tests `parse_pgn` and `select_moments` in isolation. No end-to-end graph test (TDD §13).
7. **`distill` node ignores its own structured-output schema** — `schemas.py` defines `DistillOutput` (with 2–3 takeaway validation), but `distillation.py:222-226` does raw `json.loads(response.content)` and on any decode failure silently returns zero takeaways/ops. TDD §5 specified structured output; a fenced-code-block reply from the model produces an empty (but "successful") distillation.
8. **README local-dev instructions are wrong** — README says `make dev-build` / `make dev`; the Makefile has `build` / `up` (no `dev*` targets). README says UI at `localhost:3000`; `docker-compose.yml:69` maps the frontend to **3001**.
9. **Branding D11 violated in one spot** — `app/coach/page.tsx:95` hardcodes the split wordmark `Blunder`/`standing` instead of importing `APP_NAME` from `lib/branding.ts` (which `layout.tsx` and `page.tsx` correctly use).
10. **Minor:** debug `console.log` left in `components/Chat.tsx:86`; UploadCard lacks the TDD §7 file input (paste-only); `student_rating` hardcoded to 1400 in both API routes (no UI control, which also means Maia's rating conditioning would be unused even if Maia worked).

## What was positively verified as executed (not just coded)

- Backend unit tests (27 tests: lessons, moment selector, PGN parser) and engine unit tests (16 tests incl. real Stockfish analysis) were run and **all passed** at last run (`.pytest_cache/v/cache/lastfailed` is `{}` in both projects).
- The full local stack is running under Docker Compose (backend healthy 4 days).
- ~19 real end-to-end distillation runs happened locally (Qdrant: `moments=62`, `game_summaries=19`).
- Never executed: library ingestion (`library=0`), both eval harnesses, integration test suites, lichess game fetch, any deployment, any commit.

---

## Priority order to pass certification (deadline 7pm ET 7/16)

| # | Action | Unblocks |
|---|---|---|
| 1 | `git init`-commit everything and push to a public GitHub repo | Final submission (hard gate) |
| 2 | Deploy: engine → Render, backend → LangSmith, UI → Vercel; Qdrant Cloud | Task 4 |
| 3 | Run `make ingest` against deployed Qdrant (and locally) — library is empty | Tasks 3/5/6 |
| 4 | Fix `chat.py` lessons injection (fetch `lesson_store.top()` into the prompt) | Task 2 memory requirement + core differentiator |
| 5 | Add `ragas`/`datasets`/`rank_bm25` deps; fix `run.py` to run the graph via the LangGraph server (or compile with an `InMemoryStore`); fetch benchmark games | Task 5 |
| 6 | Run baseline + ensemble retrieval eval; run planted-mistake benchmark twice (model swap); commit tables to `evals/results/` | Tasks 5 & 6 |
| 7 | Write README: Task 1 eval questions + workflow diagram; Task 2 stack list + infra & agent diagrams; Task 5/6 conclusions; fix `make dev`→`make build`/`up` and port 3001 | Tasks 1/2/5/6 |
| 8 | Record Loom; link it and all URLs in README | Final submission |
| 9 | Either fix `maia.py` against the real maia2 API or set `ENABLE_MAIA=false` and own the Stockfish-only story in the write-up | Honesty of Task 2 narrative |
| 10 | Fix the 4-vs-7 ply assertion; add the full-graph smoke test | Robustness (not cert-gating) |

---

## Changes from the prior analysis

The prior analysis was directionally right — core app substantially built, submission layer missing — and its biggest calls (lessons-injection bug, no deployments, empty `evals/results/`, thin 4-question eval set, missing README answers, the Scholar's Mate 4-vs-7 ply test bug) were all **confirmed against the code**. Corrections and material additions:

1. **Missed the biggest blocker: the repo has zero git commits and no remote.** There is no GitHub repo to submit. The prior analysis never checked.
2. **Overstated Task 6.1 as "fully implemented"** in the eval script: the ensemble path cannot even import (`rank_bm25`, `ragas`, `datasets` are undeclared in every pyproject/lockfile), and the production retriever is a commented-out stub. Task 6 is closer to MISSING than DONE-but-unrun.
3. **Missed that the planted-mistake harness crashes by construction** (direct `graph.ainvoke` without a LangGraph store → the `distill` node's injected `store` is absent). "Architecturally implemented but never executed" understated it — it cannot execute as written.
4. **Missed that the Maia-2 wrapper targets a non-existent `maia2.load()` API** — the prior marked the Maia wrapper DONE; in reality Maia can never activate, it just fails silently into the designed fallback.
5. **New positive evidence the prior lacked:** live Qdrant inspection shows `moments=62`, `game_summaries=19` — the distillation pipeline demonstrably ran E2E locally ~19 times — and pytest caches prove all unit tests passed. Conversely `library=0` **confirms** (not "presumably") the corpus was never ingested.
6. **Prior described Makefile targets that don't exist** (`dev`, `dev-build`) — and missed that README's quickstart references those same non-existent targets plus the wrong UI port (3000 vs. actual 3001).
7. **Added:** `DistillOutput` schema defined but unused (raw `json.loads` with silent-empty failure mode), D11 branding violation in `coach/page.tsx`, debug `console.log` in `Chat.tsx`, integration suites provably never run (pytest cache nodeids contain only unit tests), and `run.py`'s 5-game cap / k=2 planting vs. the TDD's 15–20 games / 2–3 misconceptions.
8. **Reframed verdicts against the official cert rubric** (workflow diagram, infra diagram, agent-workflow diagram, and eval-question list are explicit deliverables the prior treated as README polish; they are graded items and are MISSING).
