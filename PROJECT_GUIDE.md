# 🏛️ AI Validation Council — Developer Guide

> Comprehensive map of the project. Read this before touching anything.
> Looking for a quick start? See [README.md](README.md) and [USAGE.md](USAGE.md).

---

## TL;DR

Multi-agent Python 3.12 + FastAPI + LangGraph backend, Next.js 16 + Bun frontend. Validates startup ideas by pitting two adversarial LLM agents against each other and harvesting their disagreements. Phase 1 + Phase 1.5 (Traceability) shipped. 102 tests passing. Full Docker stack works end-to-end. Two known bugs in `dashboard/`. Roadmap defined across 4 phases in `README.md`.

---

## 1. PROJECT AT A GLANCE

| | |
|---|---|
| **Stack** | Python 3.12 (backend) · Next.js 16 / React 19 (frontend) · PostgreSQL · Redis · Qdrant · LangGraph 1.1 |
| **Package mgrs** | `uv` (Python) · `bun` (JS) |
| **Lint/format** | Ruff · ESLint 9 · Prettier-via-Tailwind |
| **License** | PolyForm Noncommercial 1.0.0 |
| **Tests** | 7 unit + 2 integration files (102 tests total, all passing) |
| **LOC** | ~3.5k backend, ~2.5k frontend |
| **Docker** | Full stack via `docker-compose.full.yml` + `docker-compose.dev.yml` |

---

## 2. ARCHITECTURE (5 LAYERS)

```
┌─ collectors/ ─────► Serper (Reddit) · Algolia (HN) · Crawl4AI (optional)
│
├─ knowledge/ ──────► sentence-transformers (all-MiniLM-L6-v2) → Qdrant
│
├─ agents/ ─────────► LangGraph StateGraph: 2 agents run parallel,
│                     then debate_analysis node, then optional loop
│
├─ debate/ ─────────► divergence detector (LLM, status envelope) + confidence v2 (sigmoid)
│                     + citation_verification (Module 1)
│
└─ memory/ ──────────► writeback.py (file-backed history.jsonl)
```

**Critical control flow** (`src/council/pipeline.py:21 → 89`):

1. `run_analysis(query, profile)` → `_collect_data()` (`asyncio.gather` of 3 collectors)
2. `EmbeddingPipeline.ingest_collected_data()` → Qdrant (skipped if Qdrant down)
3. `compile_council_graph().ainvoke(initial_state)` → runs 1-3 rounds of debate
4. `store_analysis_results()` → JSONL append (`data/history.jsonl`)
5. Returns dict with `agent_outputs`, `divergence_points`, `divergence_status`, `confidence_score`, `report`

**Profile → round mapping** (`council_graph.py:18-23`):

- `early_idea`: 3 rounds · `pre_launch`: 2 · `pivot`: 3 · `full`: 2 (default)

**Anti-sycophancy enforcement** (`devils_advocate.py:287-321`): 3-layer check — exact forbidden phrases, "with the right..." regex, "However, [positive sentiment]" regex, encouraging endings. On hit: log `devils_advocate_sycophancy_detected`, retry once at `temperature=0.3` with sterner prompt. On second hit: output returned with `forbidden_check_passed: false`.

**Counterfactual trigger** (`council_graph.py:111-119`): if Round 0 agreement ratio > 70%, Round 1 prompt inverted — agent told to argue **against** its own previous position. Catches premature convergence.

**Citation verification** (`debate/citation_verification.py`): every URL/title extracted from agent output is cross-checked against actually-collected Reddit posts and HN stories. Result: `{value, verified, source_type, matched_title}`. Hallucinated URLs score `verified: false` and don't inflate the confidence score. **Note**: HN discussion URLs (`item?id=...`) are stored with raw key, not normalized, because `_normalize_url()` drops query strings and all `item?id=N` URLs would collide.

**Divergence status envelope** (`debate/divergence.py`): `detect_divergence()` returns `{status: "parsed"|"parse_error"|"empty"|"insufficient_data", divergences: [...], raw: "...", error: "..."}`. Parse failures no longer silently collapse to `[]`. Status propagates through `CouncilState.divergence_status` → `report["divergence_status"]` → `/api/analyze` response.

---

## 3. WHERE TO LOOK FIRST (priority order)

| Want to… | File | Notes |
|---|---|---|
| Change how an agent thinks | `src/council/skills/{market_analyst,devils_advocate}.md` | Runtime-loaded system prompts — **no code change needed** |
| Add a new agent | `agents/your_agent.py` + `skills/your_agent.md` + wire into `council_graph.py:_run_agent_pair` | Follow node signature in `src/council/agents/AGENTS.md` |
| Tweak confidence formula | `debate/confidence.py` | v2 sigmoid non-linear penalty at line 19. Inputs are sanitized (verified citations, parsed-only divergences) |
| Add a data source | `collectors/your_collector.py` + extend `BaseCollector[T]` | Wire in `pipeline.py:_collect_data` |
| Change persistence | `memory/writeback.py` (JSONL) | Append-only analysis history |
| Edit CLI output | `cli.py:analyze()` | Uses `rich` panels/tables |
| Add API endpoint | `main.py` | Existing endpoints are inline |
| Add a settings field | `config.py:Settings` + `models/provider_config.py` + dashboard settings card | 4 places must agree |
| Touch Qdrant | `knowledge/embeddings.py` + `knowledge/qdrant_client.py` | Uses `query_points()` not `search()` |
| Change Docker stack | `Dockerfile`, `dashboard/Dockerfile`, `docker-compose.full.yml`, `docker-compose.dev.yml`, `.dockerignore` | See §11 |

---

## 4. TECH STACK — CONCRETE VERSIONS

### Backend (`pyproject.toml`)

| Lib | Version pinned | Purpose |
|---|---|---|
| `fastapi` | `>=0.115,<0.120` | HTTP API |
| `langgraph` | `>=1.1,<1.2` | State machine for council debate |
| `httpx` | `>=0.27` | OpenAI-compatible LLM calls |
| `qdrant-client[fast]` | `>=1.17,<1.18` | Vector store |
| `sentence-transformers` | `>=3.0` | Embedding model (local, offline) |
| `pydantic` / `pydantic-settings` | `>=2.2,<3.0` | Strict models |
| `sqlalchemy[asyncio]` | `>=2.0,<3.0` | Async ORM |
| `alembic` | `>=1.13` | Migrations |
| `asyncpg` | `>=0.29` | PostgreSQL driver |
| `redis` | `>=5.0` | Cache (imported, currently unused) |
| `loguru` | `>=0.7` | **Only** logger — never stdlib `logging` |
| `typer` + `rich` | latest | CLI |
| `asyncpraw` | `>=7.8,<8.0` | Imported but **not used** (Serper instead) — dead dep, remove on cleanup |
| `uuid7` | `>=0.1` | UUID7 primary keys |

### Frontend (`dashboard/package.json`)

| Lib | Version | Purpose |
|---|---|---|
| `next` | **16.2.6** ⚠ | Major breaking changes vs training data |
| `react` / `react-dom` | 19.2.4 | |
| `@base-ui/react` | ^1.4.1 | UI primitives |
| `@radix-ui/react-slot` | ^1.2.4 | |
| `shadcn` | ^4.7.0 | Component CLI |
| `tailwindcss` | ^4 | Styling |
| `lucide-react` | ^1.14.0 | Icons |
| `class-variance-authority` | ^0.7.1 | Variant styles |
| `tw-animate-css` | ^1.4.0 | Animations |

> ⚠ **Dashboard uses Next.js 16** — file conventions, routing, and `app/` patterns may differ from training data. Read `node_modules/next/dist/docs/` before editing.

---

## 5. KNOWN BUGS (must address before Phase 2)

[ ] 🐛 Bug 1: Settings page doesn't display saved models
**File:** `dashboard/src/app/settings/page.tsx` (AgentCard ~lines 100-120)

Model `<Input>` only sets `onChange`, no `value` prop binding to saved `m` state on initial render. Result: navigating to Settings after saving shows empty fields.

**Fix:** Add `value={m}` to the Input element. Same bug for all 3 AgentCards.

[Will be fixed in phase 3] 🐛 Bug 2: No live LLM thinking/streaming in analysis view
**File:** "Analysis and LLM thoughts should be reflected live, currently not showing when switching tabs. Thought section is missing entirely."

Phase 3 scope (SSE streaming per README), but current polling/post-hoc UX is jarring. Need at minimum a per-agent status indicator during the run.

### ⚠ Smaller issues

- `agents/devils_advocate.py:214-215` — `if not base_url and settings.devils_advocate_provider: base_url = settings.devils_advocate_base_url` — assigns same attribute to itself (no-op). Likely meant to look up from provider registry.
- `dashboard/src/app/settings/page.tsx` — `AgentCard` calls `onProviderChange` but parent only persists locally; no fetch reload after save.
- `confidence.py:25-30` — `debate_depth_factor` clamps `rounds <= 1` to 0 bonus. With `full` profile = 2 rounds, bonus activates Round 2 only.
- `dashboard/src/app/analysis/[id]/page.tsx` — must surface `divergence_status` badge (`parse_error` / `empty` / `parsed` / `insufficient_data`) — backend already exposes it via `/api/analyze` response.

---

## 6. CRITICAL CONVENTIONS (don't break)

From `AGENTS.md` — enforced by tests/review:

```python
# 1. ALWAYS use future annotations
from __future__ import annotations

# 2. Python 3.12+ type params, NOT Generic
class BaseCollector[T]: ...  # not Generic[T]

# 3. Pydantic v2 strict mode
class Foo(BaseModel):
    model_config = ConfigDict(strict=True)

# 4. New union syntax
x: str | None  # not Optional[str]

# 5. Async everywhere for I/O
async def foo() -> None: ...

# 6. Only Loguru
from council.logging_config import logger  # NEVER import logging

# 7. httpx only — no aiohttp
async with httpx.AsyncClient() as c: ...

# 8. Singletons via module-level pattern
_client: AsyncLLMClient | None = None
def get_llm_client() -> AsyncLLMClient:
    global _client
    if _client is None:
        _client = AsyncLLMClient()
    return _client

# 9. Agent node signature — return {"agent_outputs": [...]} only
async def agent_node(state: dict) -> dict: ...

# 10. Devil's Advocate minimums: 3 kill shots, data-backed each, no forbidden phrases

# 11. Citation contracts — citations: list[str] (legacy), citation_checks: list[dict] (Module 1)
#     citations must contain only verified values; raw hallucinated URLs go in citation_checks with verified=False
```

**Anti-patterns enforced:**

- ❌ `as any`, `@ts-ignore`, `# type: ignore`
- ❌ `Optional[X]` (use `X | None`)
- ❌ stdlib `logging`
- ❌ Committing `.env`
- ❌ Deleting failing tests
- ❌ Hardcoded system prompts in agent nodes
- ❌ Adding agents beyond the 2 existing ones before the 5 traceability modules are verified

---

## 7. STATE & DATA FLOW DETAILS

### CouncilState (`agents/state.py`)

```python
class CouncilState(TypedDict):
    query: str
    reddit_posts: list[dict]
    hn_stories: list[dict]
    crawl_results: list[dict]
    enabled_sources: list[str]
    agent_outputs: Annotated[list[dict], operator.add]  # KEY: parallel append
    divergence_points: list[dict]
    divergence_status: str | None                       # "parsed"|"parse_error"|"empty"|"insufficient_data"
    confidence_score: float
    round: int
    error: str | None
    chunk_count: int
    report: dict | None
    counterfactual_triggered: bool
    profile: str
```

### Confidence Score v2 (`debate/confidence.py:38-68`)

```
volume   = 30 / (1 + exp(-0.03 * (data_volume - 40)))     # sigmoid saturating
diversity = 20 * (min(sources, enabled) / max(enabled, 1))
recency   = 20 * recency_score                            # 0.0–1.0
penalty   = 25 / (1 + exp(-1.5 * (divergences - 3)))      # non-linear divergence
depth     = 10 * (2*convergence - 1) * ln(rounds+1)/ln(3) # bonus if converging
quality   = min(10, verified_citation_count * 1.5)        # Module 4: only verified

raw = volume + diversity + recency - penalty + depth + quality
clamp(0, 100)
```

**Input sanitization (Module 4):**

1. `quality` counts only **verified** citations. `_count_verified_citations(agent_outputs)` iterates `citation_checks[]` for `c.get("verified") == True`. Falls back to `len(citations)` when `citation_checks` is absent (legacy analyses).
2. `penalty` only consumes `divergence_count` when `divergence_status == "parsed"`. On `"parse_error"`, `divergence_count` is set to 10 (max penalty) and a `divergence_status_parse_error` warning is logged.
3. On `"insufficient_data"` or `"empty"`, `divergence_count` is 0 — no penalty. This is intentional: empty consensus means agents didn't disagree, not that they crashed.

**Key insight:** High divergence → low score, even with lots of data. Intentional — "honest uncertainty."

---

## 8. INFRASTRUCTURE — 3 RUN MODES

### Option 1: No Docker (host terminal for everything)

```bash
# Install infrastructure natively
brew install postgresql@16 redis qdrant
brew services start postgresql@16 redis
qdrant &                                       # binary

# App
uv sync
cp .env.example .env
uv run alembic upgrade head
PYTHONPATH=src uv run uvicorn council.main:app --port 8000 --reload   # terminal 1
cd dashboard && bun install && bun run dev                            # terminal 2
```

### Option 2: Mixed (docker infra + host apps — best for hot-reload dev)

```bash
docker compose up -d                              # postgres + redis + qdrant
uv sync && cp .env.example .env
uv run alembic upgrade head
PYTHONPATH=src uv run uvicorn council.main:app --port 8000 --reload   # terminal 1
cd dashboard && bun install && bun run dev                            # terminal 2
```

### Option 3: Full Docker (single command, production parity)

```bash
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml up --build -d
open http://localhost:3000
```

See [USAGE.md](USAGE.md) for full step-by-step.

### Services (compose-managed)

| Service | Image | Port | Healthcheck |
|---|---|---|---|
| Postgres | `postgres:16-alpine` | 5432 | `pg_isready -U council -d council` |
| Redis | `redis:7-alpine` (appendonly) | 6379 | `redis-cli ping` |
| Qdrant | `qdrant/qdrant:v1.17.0` | 6333/6334 | bash `/dev/tcp` → `/healthz` (qdrant image has no curl) |
| Backend | `council-backend:latest` (built from `Dockerfile`) | 8000 | `GET /health` |
| Dashboard | `council-dashboard:latest` (built from `dashboard/Dockerfile`) | 3000 | implicit (Next.js) |

**Graceful degradation:** every external service wrapped in try/except. App works without Docker. Tests use heavy mocking.

---

## 9. RUNNING LOCALLY (already-installed env)

`.venv` exists, uv + bun + docker present.

```bash
# Quick CLI test (requires .env with LLM_API_KEY or dashboard-configured key)
PYTHONPATH=src uv run python -m council analyze "an AI CRM for dentists"

# Tests
uv run pytest tests/unit -v          # 7 files
uv run pytest tests/integration -v   # 2 files (mocked, no Docker needed)

# Lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Frontend
cd dashboard && bun install && bun run dev
```

`.venv` is provisioned but dev tools (ruff, pytest) may need `uv pip install ruff pytest pytest-asyncio` if not already present (pyproject.toml declares them under `[project.optional-dependencies]`, which uv doesn't auto-install in some modes).

---

## 10. ROADMAP

| Phase | Status | Deliverables | Effort |
|---|---|---|---|
| **1 — Core Skeleton** | ✅ Done | CLI, 2 agents, Reddit/HN collectors, divergence detection, confidence v2, Next.js dashboard | shipped |
| **1.5 — Traceability** | ✅ Done | Citation verification (Module 1), JSONL history (Module 2), parse-error envelopes (Module 3), confidence sanitization (Module 4), retry loops (Module 5) | shipped |
| **Bug fixes (now)** | 🔜 | Fix Settings page model display · Add minimal streaming indicator · Surface `divergence_status` badge in dashboard · Resolve `devils_advocate.py:214-215` no-op | 1-2 days |
| **2 — Full Council** | 🔜 | Add `ICP Specialist` agent · Add `Competitive Intel` agent · Enable multi-round debate toggle · Wire Redis cache layer (imported, unused) | 2-3 weeks |
| **3 — Simulation + UI** | 🔜 | SSE streaming for live LLM thought · Monte Carlo scenarios · GTM simulations · Per-agent real-time thinking panels | 3-4 weeks |
| **4 — Deploy + Polish** | 🔜 | PDF report generation · User accounts (User model exists, unused) · Cost dashboard · Railway deploy · CI/CD · Auth | 4-6 weeks |

### Suggested immediate ordering

1. **Fix Settings bug** (cosmetic, blocks user trust — 30 min)
2. **Add `divergence_status` badge to analysis page** (5 min, backend already exposes it)
3. **Add minimal live status indicator** (UX — 2 hrs)
4. **Implement Redis caching of repeated queries** (uses already-imported lib, saves API $$)
5. **Add `ICP Specialist` agent** (high value, low risk — copy DevilsAdvocate pattern)
6. **Multi-round debate toggle in UI** (already backend-supported via profile)
7. **Add CI/CD** (no `.github/workflows/` directory exists yet)
8. Then Phase 3 streaming + Phase 4 deploy

---

## 11. DOCKER DEEP-DIVE

### Files

| File | Purpose |
|---|---|
| `Dockerfile` (root) | Backend image. `python:3.12-slim` base, uv-managed venv at `/app/.venv`. Path includes `/usr/sbin` so `groupadd`/`useradd` resolve. Optional `INSTALL_PLAYWRIGHT=1` build-arg adds Playwright deps for crawl4ai. Runs as non-root `appuser` (uid 1000). |
| `dashboard/Dockerfile` | Dashboard image. `oven/bun:1.3.14-alpine` base (1.1.x can't read this lockfile format). `NEXT_PUBLIC_API_URL` baked in at build time. Single-stage for now — `output: standalone` not configured. Runs as non-root `appuser` (uid 1001 — bun image already has uid 1000). |
| `docker-compose.yml` | Infra-only: postgres + redis + qdrant for host-mode dev. |
| `docker-compose.full.yml` | Full stack: backend + dashboard + 3 infra services. DNS-aware URL overrides (`postgres://`, `redis://`, `qdrant://`). |
| `docker-compose.dev.yml` | Dev overlay: exposes ports 8000 and 3000 on host, sets `NEXT_PUBLIC_API_URL=http://localhost:8000`. Excluded from production. |
| `.dockerignore` (root) | Excludes `.venv/`, `.git/`, `dashboard/`, `__pycache__/`, etc. ~50 KB context instead of 4+ GB. |
| `dashboard/.dockerignore` | Excludes `node_modules/`, `.next/`, etc. |

### Why Qdrant healthcheck uses bash + /dev/tcp

Qdrant image (`qdrant/qdrant:v1.17.0`) ships only with its own binary. No `curl`, no `wget`, and `/bin/sh` is busybox which doesn't have `/dev/tcp`. The healthcheck command explicitly invokes `/usr/bin/bash` (which Qdrant does include) and uses bash's `/dev/tcp` to probe `/healthz`:

```yaml
test: ["CMD", "bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/6333 && echo -e 'GET /healthz HTTP/1.0\\r\\nHost: localhost\\r\\n\\r\\n' >&3 && grep -q '200' <&3"]
```

### Why `INSTALL_PLAYWRIGHT=0` default

Playwright + Chromium is ~400 MB and ~3 min of build time. The crawl4ai collector is the only consumer and it's not in pyproject deps. Set `INSTALL_PLAYWRIGHT=1` only if you enable the crawl4ai collector.

### Why Bun 1.3.14 in dashboard image (not latest stable)

The project's `dashboard/bun.lock` is in `lockfileVersion: 1` format (older bun text lockfile). Bun 1.1.x reads it as binary and refuses to install. Bun 1.3.x reads it correctly. The Dockerfile `ARG BUN_VERSION=1.3.14` pins this. If you `bun upgrade` and regenerate the lockfile, bump the arg.

### Build time expectations

- **First build**: 2-3 min (downloads ~3 GB of Python wheels including torch).
- **Code-only rebuild** (no pyproject/uv.lock changes): <30 s (layer cache hits).
- **Dashboard build**: ~30 s (bun install + Next.js build).
- **Cold docker compose up**: ~30 s for infra services to become healthy; backend takes another 10-20 s.

### Why `docker-compose.dev.yml` and not `docker-compose.override.yml`

Docker Compose v2 auto-merges `docker-compose.override.yml` with `docker-compose.yml` whenever you run `docker compose up -d` with no `-f` flag. This is hostile to Option 2 users: the dev overlay references a `backend` service that doesn't exist in the infra-only base file, so plain `docker compose up -d` errors with "service backend has neither an image nor a build context specified."

Renaming to `docker-compose.dev.yml` makes the file opt-in only when you pass `-f docker-compose.dev.yml` explicitly. No surprises for anyone running the default file.

---

## 12. TESTING REALITY CHECK

Current state:

| File | Type | Tests |
|---|---|---|
| `tests/unit/test_forbidden.py` | Anti-sycophancy | 10 |
| `tests/unit/test_confidence.py` | Score formula + sanitization | 19 (incl. Module 4) |
| `tests/unit/test_config.py` | Settings | 5 |
| `tests/unit/test_divergence.py` | LLM parsing + envelope | 15 |
| `tests/unit/test_protocols.py` | Round/word-limit logic | 9 |
| `tests/unit/test_report.py` | SWOT/debate summary | 7 |
| `tests/unit/test_citation_verification.py` | Citation verification (Module 1) | 12 |
| `tests/unit/test_history_persistence.py` | JSONL history (Module 2) | 8 |
| `tests/unit/test_market_analyst_retry.py` | Retry loop (Module 5) | 11 |
| `tests/unit/test_devils_advocate_retry.py` | Sycophancy retry (Module 5) | 5 |
| `tests/integration/test_pipeline.py` | End-to-end with mocks | 2 |
| **Total** | | **102** |

All integration tests **fully mock** external services — no Docker required. Good for CI. But no live collector tests, no live LLM tests, no frontend tests.

**Add when expanding:**

- Per-collector live integration test (Serper/HN) gated by env var
- Frontend component tests (Vitest + RTL — not configured)
- E2E Playwright test for analyze→history flow

---

## 13. SECURITY / RISK NOTES

1. **`/api/analyze` is unauthenticated.** No JWT, no API key check. Anyone can spend your LLM budget. The `User` model exists in `models/db.py` but is unused.
2. **CORS allows `*` in development** (`main.py:120`). Tighten for production.
3. **API keys are masked in GET responses** but stored in plaintext JSON at `data/app_settings.json` (gitignored, still risky on shared hosts).
4. **Cost tracking exists** (`llm/client.py:_UsageRecord`) but `cost` is hardcoded to `0.0`. Real pricing model not implemented.
5. **`asyncpraw` is in deps but unused** — dead dependency, remove on next cleanup pass.
6. **`DataProviderConfig` is created but never written back to persisted `data/app_settings.json`** (`config.py:get_app_config()` builds it but `_persist_settings` doesn't include it). So `enable_*` toggles survive restart but aren't bundled with agent configs cleanly.
7. **`.env` contains the real `SERPER_API_KEY`** by convention — never commit `.env` (gitignored). If you fork or push to a public repo, scrub it.

---

## 14. ONE-LINER COMMANDS CHEATSHEET

```bash
# Backend
uv run python -m council analyze "your idea"
PYTHONPATH=src uv run uvicorn council.main:app --port 8000
uv run pytest tests/ -v
uv run ruff check src/ tests/

# Database
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "msg"

# Docker
docker compose up -d                                    # postgres + redis + qdrant only
docker compose down -v                                  # wipe data
docker compose -f docker-compose.full.yml build         # build backend + dashboard images
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml up -d   # full dev stack

# Frontend
cd dashboard && bun install && bun run dev
cd dashboard && bun run build && bun run start
cd dashboard && bun run lint

# Validation helpers
uv run python scripts/smoke_test.py
```

---

## RECOMMENDATION

For the **next session**:

1. **Read `src/council/skills/devils_advocate.md` end-to-end** — project's soul. Understanding it = understanding the entire product.
2. **Read `src/council/agents/council_graph.py`** — only 220 lines, encapsulates entire council logic.
3. **Run `uv run pytest tests/unit -v`** to see current state.
4. **Fix the bugs in §5 first** — they block user trust.
5. Then pick Phase 2 scope: start with **Redis caching of identical queries** (already half-wired, immediate $$ savings) before adding new agents.

Pick a direction — will create detailed plan + execute.