# TDD — Chess Tutor Agent (POC)

**Status:** Draft for review, 2026-07-08
**Deadline:** Certification Challenge submission due **Tuesday, July 14, 2026**
**Upstream docs:** [`PRD.md`](PRD.md) (what & why), [`CONTEXT.md`](CONTEXT.md) (ubiquitous language), [`docs/adr/`](docs/adr/) (ADR 0001 library licensing, ADR 0002 three-service topology), [`00_Docs/Certification Challenge/README.md`](<00_Docs/Certification Challenge/README.md>) (rubric)

This document says **how** to build the simplest POC that satisfies every
certification task. It follows the PRD exactly (Maia-2 + Stockfish, three
services). Where the PRD left implementation open, §9 records the decision
and the reason. Anything not needed to pass a cert task is out (§10).

---

## 1. Repo & project layout

The POC lives in a **new dedicated public GitHub repo** named
`chess-tutor`. The user-facing product title is **Blunderstanding**;
that name appears only in the UI (and the chat persona), never in code
identifiers, package names, or infra — so rebranding is a one-line
change (D11). The course fork stays as reference material only; PRD,
CONTEXT, ADRs, and this TDD are copied into the new repo. The final
written submission doc and Loom link live at the new repo's root.

```
chess-tutor/
├── README.md                  # submission doc: tasks 1–7 answers + Loom link
├── PRD.md  TDD.md  CONTEXT.md
├── docs/adr/
├── agent/                     # LangGraph app → LangSmith deployment
│   ├── langgraph.json         # graphs: distillation, chat (session 09 shape)
│   ├── pyproject.toml         # torch-free (ADR 0002)
│   └── app/
│       ├── graphs/distillation.py
│       ├── graphs/chat.py
│       ├── tools.py           # 5 chat tools
│       ├── engine_client.py   # HTTP client for the Engine Service
│       ├── lessons.py         # Lesson store ops (LangGraph Store)
│       ├── retrieval.py       # Qdrant collections, embedders, retrievers
│       ├── schemas.py         # Pydantic: Moment, Takeaway, Lesson, LessonOp…
│       └── prompts.py
├── engine-service/            # FastAPI → Render (CPU)
│   ├── Dockerfile             # apt stockfish + pip maia2 (torch cpu)
│   ├── main.py
│   └── tests/
├── web/                       # Next.js → Vercel
│   ├── app/                   #   pages + API proxy routes
│   ├── components/            #   BoardPanel, Chat, UploadCard, TakeawayList
│   └── lib/branding.ts        #   APP_NAME = "Blunderstanding" (single source, D11)
├── scripts/
│   ├── ingest_library.py      # Gutenberg → Qdrant `library`
│   └── fetch_lichess_games.py # CC0 games for the benchmark
└── evals/
    ├── retrieval_ragas.py     # Task 5.1 / Task 6.1 referee
    ├── planted_mistakes/      # Task 5.2 / Task 6.2 referee
    └── results/               # committed CSV/markdown tables
```

Python 3.13 + `uv` throughout (matches course sessions); `agent/` and
`engine-service/` are separate uv projects because the agent image must
stay torch-free (ADR 0002).

## 2. System topology (ADR 0002)

```
Browser (laptop/phone)
   │ HTTPS
   ▼
Vercel: Next.js UI ── /api/* proxy (LangGraph SDK, server-side key)
   │                                            │
   ▼                                            ▼
LangSmith: LangGraph deployment          (LangSmith tracing)
   ├── graph `distillation`  ── HTTP ──▶ Render: Engine Service (FastAPI)
   ├── graph `chat`          ── HTTP ──▶     ├── Stockfish (apt binary + python-chess)
   ├── checkpointer (managed Postgres)       └── Maia-2 (pip maia2, CPU torch)
   └── cross-thread Store: Lessons
   │
   ▼
Qdrant Cloud (free tier): library / moments / game_summaries
   │
LLM + embeddings: Vercel AI Gateway (OpenAI-compatible /v1)
Web search: Tavily
```

The browser only ever talks to Vercel. All keys (LangSmith, gateway,
Qdrant, Tavily) are server-side. The Engine Service is the only
component the agent calls over plain HTTP; it is stateless and holds no
secrets beyond an optional shared bearer token.

## 3. Engine Service (Render, CPU)

Barebones FastAPI. One Docker image: `apt-get install stockfish`,
`pip install maia2 python-chess fastapi uvicorn` with CPU-only torch.
Maia-2 model weights download at build time (baked into the image) so
cold starts don't re-fetch. Render Starter instance (512MB is too small
for torch + Maia-2; use 2GB). Health check `GET /healthz`.

### Endpoints

`POST /analyze/game` — the distillation workhorse. **One call per
upload**, not one per position.

```jsonc
// request
{ "pgn": "...", "student_color": "white", "student_rating": 1400,
  "depth": 14, "maia_top_k": 5 }
// response
{ "plies": [ {
    "ply": 12, "san": "Qxd5", "uci": "d1d5", "fen_before": "...", "fen_after": "...",
    "eval_before_cp": 35, "eval_after_cp": -80,        // white POV, mate → ±10000
    "best_move_uci": "c3d5", "best_line_san": ["Nxd5", "..."],
    "cp_loss": 115,                                     // student POV; null for opponent plies
    "maia": { "top_moves": [{"uci": "d1d5", "prob": 0.42}, ...],
              "played_prob": 0.42, "win_prob": 0.61 }   // only computed for student plies
  }, ... ] }
```

Stockfish: `chess.engine.SimpleEngine`, fixed depth 14 (~80 plies ≈
tens of seconds on Render CPU; acceptable inside an async distillation
run). Maia-2 conditioned on `student_rating` (POC default 1400).

`POST /analyze/position` — the chat tool. `{ "fen", "student_rating" }`
→ `{ "eval_cp", "best_move_san", "best_line_san", "maia": {...} }`.
Single position, depth 16.

**Maia-2 fallback (PRD risk #1):** `maia` fields are nullable. If Maia-2
fails to load or errors, the service sets `maia: null` and keeps
serving Stockfish; agent prompts already treat Maia data as optional
("when available, say how findable the move was at the Student's
level"). Dropping Maia is a config flag, not a code change downstream.

## 4. Data model

### Qdrant collections (Qdrant Cloud free tier)

All vectors: `text-embedding-3-small` (1536-d, cosine) via the gateway.
The embedded text is always a natural-language paragraph — the
describe-then-embed proxy from the PRD.

| Collection | Embedded text | Payload |
|---|---|---|
| `library` | book section chunk | `book`, `author`, `section_title`, `license`, `source_url` |
| `moments` | LLM-written Moment description | `user_id`, `game_id`, `ply`, `fen`, `move_san`, `annotation` (nullable), `cp_loss`, `best_move_san`, `maia_played_prob` |
| `game_summaries` | LLM-written Game Summary | `user_id`, `game_id`, `date`, `result`, `opening`, `takeaways` (list of strings) |

`moments` and `game_summaries` searches always filter
`user_id == <current user>`. `library` is shared, no filter.

### Lessons (LangGraph cross-thread Store — the required memory component)

Namespace `(user_id, "lessons")`, key = `lesson_id` (uuid). Value:

```jsonc
{ "name": "Trades pieces to 'simplify' while already worse",
  "description": "…one paragraph, correctable-habit level…",
  "recurrence": 3, "status": "active",            // active | retired
  "evidence": [ {"game_id": "...", "ply": 24}, ... ],
  "created_at": "...", "updated_at": "..." }
```

`lessons.py` exposes exactly the coach's-notebook verbs from CONTEXT.md:
`reinforce(id, evidence)`, `create(...)`, `merge(ids, new)`,
`rename(id, name)`, `retire(id)`, plus `top(user_id, n=10)` ordered by
recurrence. The LLM chooses ops (§5 node 5); this module applies them —
judgment in the model, bookkeeping in code.

### Conversation memory

LangSmith deployments provide a managed Postgres checkpointer and Store
automatically — no persistence infra to build. One chat thread per
user per game review; `thread_id` minted by the UI on upload.

## 5. Distillation subgraph (deterministic pipeline, LLM nodes inside fixed edges)

Input: `{ user_id, pgn, student_color, student_rating }`. Linear graph —
no conditional edges:

```
parse_pgn → engine_pass → select_moments → describe_moments → distill → summarize_and_index
```

1. **`parse_pgn`** (pure code, python-chess): moves, headers, and PGN
   comments attached to plies → Annotations. Empty comments ⇒ Bare Game;
   set `annotated: false` (degraded mode only changes prompt wording
   downstream — "no student thoughts available").
2. **`engine_pass`** (code): one `POST /analyze/game`. Retry ×3 with
   backoff (Render cold start ~30s on first hit).
3. **`select_moments`** (pure code, deterministic and unit-testable):
   student plies with `cp_loss ≥ 150`, ranked by cp_loss, cap 6, floor 3
   (pad with next-largest swings). Any annotated ply with
   `cp_loss ≥ 75` is force-included — annotated mistakes are the whole
   point of the product.
4. **`describe_moments`** (LLM, structured output): one paragraph per
   Moment describing position, the move, the Student's stated thinking,
   and the engine verdict in prose. These paragraphs are what gets
   embedded.
5. **`distill`** (LLM, structured output): input = Moment paragraphs +
   Annotations + the Student's current active Lessons (full list from
   Store). Output schema:
   `{ takeaways: [ {text, moment_ply} ]  # 2–3`,
   `lesson_ops: [ {op: reinforce|create|merge|rename|retire, ...} ] }`.
   Prompt carries the correctable-habit rubric verbatim from CONTEXT.md
   ("not a topic, not a single position") — this is the PRD's named
   mitigation for Lesson granularity drift. Ops are applied via
   `lessons.py`; malformed ops are dropped and logged, never crash the run.
6. **`summarize_and_index`** (LLM + code): write the Game Summary
   paragraph; embed and upsert Moments → `moments`, summary →
   `game_summaries`. Return `{ takeaways, summary, moments, lessons_top10 }`
   as the run output for the UI.

Expected wall time ≈ 1–3 min (engine pass dominates). Runs execute as
LangGraph **background runs**; the UI polls (§7).

## 6. Chat subgraph (single tool-calling agent)

`create_react_agent` over the gateway chat model, with a structured
`response_format` so the UI never regex-parses FENs:

```python
class TutorReply(BaseModel):
    reply: str                      # markdown, shown in chat
    positions: list[BoardRef] = []  # BoardRef = {fen: str, caption: str}
```

**System prompt assembly (per turn, code not tools):** persona (coach
for an adult improver) + the Student's **top 10 Lessons by Recurrence**
injected verbatim + the current game's Summary and Takeaways (looked up
by `game_id` from the run context). Injecting Lessons instead of making
them a tool guarantees the coach's working picture is always present —
the PRD's core differentiator can't be skipped by a lazy tool-caller.

**Grounding rule in the prompt:** every concrete chess claim (evals,
"loses a pawn", best moves) must come from an engine tool result; the
LLM decides what to teach, the engine decides what is true.

**Tools** (`user_id`/`student_rating` injected from run context — never
model-supplied):

| Tool | Backend | Purpose |
|---|---|---|
| `analyze_position(fen)` | Engine Service `/analyze/position` | objective eval + human-findability |
| `search_moments(query)` | Qdrant `moments`, k=4, user-filtered | "have I been in trouble like this before?" |
| `search_games(query)` | Qdrant `game_summaries`, k=3, user-filtered | game-level recall |
| `search_library(query)` | Qdrant `library`, k=4 | cite the classics (return payload for attribution) |
| `web_search(query)` | Tavily (`langchain-tavily`) | modern/live content; the cert's external API |

No multi-agent (PRD §4). Checkpointer gives within-thread memory for free.

## 7. Web UI (Next.js on Vercel)

App Router; `react-chessboard` + `chess.js`; Tailwind (crib session 09
frontend). Responsive: board stacks above chat below `md` (PRD's
phone-and-laptop requirement).

**Branding:** `web/lib/branding.ts` exports `APP_NAME = "Blunderstanding"`
(plus tagline). Every user-visible occurrence — page `metadata` title,
header wordmark, empty states — imports it; nothing hardcodes the name.
The agent's persona prompt takes the app name from an `APP_NAME` env var
with the same value, so the tutor introduces itself consistently.

**Screens**

- `/` — username field, no password; stored in `localStorage`; router
  push to `/coach`. Username is the persistence key everywhere.
- `/coach` — three areas:
  - **UploadCard**: paste-PGN textarea + file input; White/Black toggle
    (pre-filled by matching username against PGN `White`/`Black`
    headers). On submit: create distillation run → show progress state
    → render Takeaways when done.
  - **BoardPanel** (read-only): renders the current game with ⏮ ◀ ▶ ⏭
    steppers via chess.js; when a chat reply carries `positions[]`,
    each renders as a clickable chip that sets the board to that FEN.
  - **Chat**: streaming transcript against the game's thread.

**API routes (passthrough proxy — the browser never sees keys)**

| Route | Does |
|---|---|
| `POST /api/upload` | LangGraph SDK: create background run on `distillation` → `{run_id, thread_id}` |
| `GET /api/upload/[runId]` | poll run status; on success return distillation output |
| `POST /api/chat` | `client.runs.stream(thread_id, "chat", ...)` → SSE passthrough |

Background-run + polling (not a single long request) because
distillation exceeds default serverless timeouts; chat streams normally.

## 8. Ingestion & offline scripts

**`scripts/ingest_library.py`** — Project Gutenberg, public domain
(ADR 0001): Capablanca *Chess Fundamentals*, Lasker *Common Sense in
Chess*, + one more classic if chunk count feels thin. Strip Gutenberg
header/footer boilerplate; chunk by the books' own section/chapter
headings (the PRD's "natural unit" strategy — instructional books are
already organized as one idea per section); sections > ~1500 tokens get
`RecursiveCharacterTextSplitter` (1000/100) within the section, payload
preserved. Idempotent upsert (deterministic ids = hash of book+section).
Run once from a laptop; the corpus is static for the POC.

**`scripts/fetch_lichess_games.py`** — pull one month of the CC0
lichess database, filter both players < 1500 rapid, sample ~20 games
with 30–60 moves, save PGNs to `evals/planted_mistakes/games/`.

## 9. Decisions this TDD fixes (PRD was silent)

| # | Decision | Why |
|---|---|---|
| D1 | Batch `/analyze/game` endpoint; one HTTP call per upload | 80 per-position calls × network latency dominates distillation time; batching is also the natural retry unit |
| D2 | Student color: UI toggle, pre-filled from PGN name headers | Inferring color reliably is a rabbit hole; a toggle is one click and always right |
| D3 | Moment selection is pure code (threshold + cap), not an LLM node | Deterministic, unit-testable, and the benchmark needs stable moment selection to attribute Takeaway misses correctly |
| D4 | Top-10 Lessons injected into the chat system prompt, not a tool | Guarantees the persistent-coach picture is in every reply; one less tool to eval |
| D5 | Distillation as background run + UI polling | Exceeds serverless request timeouts; polling is the simplest robust shape |
| D6 | Chat replies use structured `response_format` with `positions[]` | PRD requires FEN "in a structured field"; UI stays regex-free |
| D7 | Embeddings also routed through Vercel AI Gateway | One key, one bill, satisfies the gateway requirement uniformly |
| D8 | Qdrant Cloud free tier | Zero ops; 1GB ≫ POC corpus; same client code as course sessions |
| D9 | Maia fields nullable end-to-end; disable via env flag | Makes the PRD's "dropping Maia = deleting an endpoint" literally true |
| D10 | Fixed Stockfish depth 14 (game pass) / 16 (chat) | Predictable latency on CPU; depth beats movetime for reproducible evals in the benchmark |
| D11 | Repo/infra named `chess-tutor`; product title "Blunderstanding" only via `web/lib/branding.ts` + `APP_NAME` env var | Title is a brand decision that may change; keeping it out of identifiers makes a rename a one-line edit, not a refactor |

## 10. Out of scope (beyond PRD §7)

No auth, no rate limiting, no PGN-size hardening beyond a 100KB/one-game
cap, no multi-game upload, no streaming distillation progress detail
(just run status), no board interactivity, no i18n, no dark mode work
beyond defaults.

## 11. Evaluation harness (Task 5) and improvements (Task 6)

### 11.1 Retrieval eval — `evals/retrieval_ragas.py`

Sessions 05/06 pattern. Test set: Ragas `TestsetGenerator` over
`library` chunks (~40 QA pairs) **plus** ~12 hand-written golden
questions over `moments`/`game_summaries` built from the benchmark
games (these double as Task 1's evaluation questions). Metrics:
faithfulness, answer relevancy, context precision, context recall.
Runner takes a retriever-config flag so baseline vs. advanced is one
CLI switch; emits a markdown table to `evals/results/`.

### 11.2 Planted-mistake benchmark — `evals/planted_mistakes/`

1. ~15–20 CC0 lichess games (§8), engine-passed to find real mistakes.
2. **Misconception catalog** (~8 entries, e.g. "trades to simplify while
   worse", "counts attackers not defenders", "grabs material ignoring
   development", "assumes a threat without checking it works").
3. An LLM writes synthetic Student Annotations onto each game,
   embedding 2–3 cataloged misconceptions at engine-confirmed mistake
   plies; the planted labels are saved as ground truth.
4. Run the real distillation graph per game (fresh benchmark user_id).
5. Score: **Takeaway precision/recall** vs. planted misconceptions
   (LLM-judge matching, `gpt-5.4` as judge ≠ generation model) + a
   0–3 coaching rubric per Takeaway (specific? actionable?
   position-grounded?).
6. Sanity anchor: run the developer's own real annotated games and
   eyeball the Takeaways before trusting synthetic numbers.

### 11.3 Task 6 (pre-committed in PRD §6)

1. **Advanced retriever:** BM25 + dense `EnsembleRetriever` (session 07
   `lib/`) on `library` (and `moments`); chess vocabulary
   ("Caro-Kann", "f7", "skewer") is exact-match-sensitive. Referee:
   §11.1 table before/after. Cohere rerank stacks on top only if the
   ensemble underwhelms.
2. **Other component:** distillation model swap through the gateway
   (`openai/gpt-5.4-mini` → stronger model, one env var). Referee:
   §11.2 precision/recall + rubric before/after.

## 12. Configuration

| Variable | Used by | Notes |
|---|---|---|
| `AI_GATEWAY_API_KEY`, `AI_GATEWAY_BASE_URL` | agent, evals | OpenAI-compatible `/v1`; `ChatOpenAI(base_url=…, model="openai/gpt-5.4-mini")` |
| `CHAT_MODEL`, `DISTILL_MODEL`, `EMBED_MODEL` | agent, evals | model ids as gateway strings; Task 6.2 = change `DISTILL_MODEL` |
| `QDRANT_URL`, `QDRANT_API_KEY` | agent, scripts, evals | |
| `ENGINE_SERVICE_URL`, `ENGINE_SERVICE_TOKEN` | agent | token = shared bearer, optional |
| `ENABLE_MAIA` | engine-service | D9 kill switch |
| `TAVILY_API_KEY` | agent | |
| `APP_NAME` | agent | product title in the persona prompt; defaults to "Blunderstanding" (D11) |
| `LANGSMITH_API_KEY`, `LANGSMITH_TRACING` | agent, evals | tracing = monitoring deliverable |
| `LANGGRAPH_API_URL`, `LANGSMITH_API_KEY` | web (server-side only) | proxy credentials |

## 13. Testing strategy

Deterministic code gets real tests; LLM behavior is refereed by §11, not
unit tests.

- **engine-service:** endpoint tests with a fixed short PGN — schema,
  known mate eval, cp_loss sign correctness for both colors (the classic
  POV bug); Maia-disabled path returns `maia: null`.
- **agent:** unit tests for `parse_pgn` (annotations extracted, Bare
  Game detected), `select_moments` (threshold/cap/force-include rules),
  and `lessons.py` ops (recurrence math, merge/retire). Graph smoke test
  with a mocked engine client + `FakeListLLM` — the full distillation
  graph runs end-to-end in CI with zero network.
- **web:** manual test script in README (upload → takeaways → chat →
  board chip) on laptop + phone; not worth automation in a 6-day POC.
- **Smoke eval:** 3-game mini version of §11.2 runs on demand as the
  "did I break distillation" check while iterating.

## 14. Build order (6 days)

Each day ends with something deployed or measurable; every step cribs
named course code (PRD risk table).

| Day | Deliverable | Cribs |
|---|---|---|
| **1 (Wed)** | New repo scaffolded; Engine Service with `/analyze/game` (Stockfish) live on Render; `ingest_library.py` run — Qdrant `library` populated | 01 (Qdrant), ADR 0002 |
| **2 (Thu)** | Distillation graph end-to-end locally (real engine service); Lessons ops + tests green | 02, 03 (Store) |
| **3 (Fri)** | Chat agent + 5 tools locally; both graphs deployed to LangSmith; Maia-2 endpoint added to Engine Service | 09 (deploy), 06 (gateway) |
| **4 (Sat)** | Next.js UI on Vercel: upload → poll → takeaways; chat + board; works on phone. **Public E2E demo exists** | 09 frontend |
| **5 (Sun)** | Eval harness both parts; baseline numbers committed to `evals/results/` | 05, 06 |
| **6 (Mon)** | Task 6: ensemble retriever + model swap, before/after tables; README write-up; Loom | 07 |
| **Tue** | Buffer + submission | — |

Cut lines if behind, in order: Cohere rerank (already optional) →
Maia-2 (D9 flag) → golden Moments questions in Ragas set (keep the
Library synthetic set) → third Library book.

## 15. Cert-task acceptance check

| Cert task | Satisfied by |
|---|---|
| 1 Problem/audience + eval questions | PRD §1; §11.1 golden questions + §11.2 planted set |
| 2 Solution, infra diagram, agent workflow, gateway/memory/browser | §2 topology (gateway D7, Lessons §4, phone §7); §5–6 = workflow diagram source |
| 3 Data, chunking, external API | §4 collections; §8 chunking rationale; Tavily §6 |
| 4 E2E prototype, public deploy | Day-4 milestone: Vercel + LangSmith + Render, public URL |
| 5 Test set + harness + conclusions | §11.1 + §11.2; conclusions written from `evals/results/` |
| 6 Advanced retriever + second improvement, tables | §11.3, refereed by the two harnesses |
| 7 Next steps | PRD §7, restated in README |
