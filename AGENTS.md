# PROJECT KNOWLEDGE BASE

**Generated:** 2026-05-11
**Commit:** c3fc8e3
**Branch:** main

## OVERVIEW

Multi-agent AI council that validates startup ideas through adversarial debate with real-time
Reddit/HN data. Python 3.12+, FastAPI + LangGraph orchestration, any OpenAI-compatible
LLM provider.

## STRUCTURE

```
council/
├── src/council/           # Python package (src-layout)
│   ├── cli.py             # Typer CLI entry: `python -m council analyze "idea"`
│   ├── pipeline.py        # End-to-end orchestrator (collect → embed → council → debate → write)
│   ├── main.py            # FastAPI app: /health, /docs
│   ├── config.py          # Pydantic v2 Settings from .env
│   ├── agents/            # LangGraph council graph + 2 agent nodes → AGENTS.md
│   ├── collectors/        # Reddit (Serper) + HN (Algolia) data ingestion
│   ├── debate/            # Divergence detector + confidence score formula
│   ├── llm/               # OpenAI-compatible async client (retry, cost tracking)
│   ├── memory/            # MemPalace verbatim storage + analysis writeback
│   ├── models/            # Pydantic (data/analysis) + SQLAlchemy (db) models
│   │   ├── report.py        # AnalysisReport, DebateSummary, SWOTAnalysis, CouncilAddendum
│   │   └── provider_config.py  # AgentProviderConfig, DataProviderConfig
│   └── skills/            # Agent cognitive manuals (markdown, loaded at runtime)
├── tests/                 # unit/ (isolated) + integration/ (pipeline-level, fully mocked)
├── alembic/               # Async PostgreSQL migrations
├── scripts/               # validate_phase1.py, smoke_test.py
├── dashboard/             # Next.js 14 web UI (bun, shadcn/ui, Tailwind dark theme)
├── pyproject.toml         # UV-managed, Ruff, pytest, coverage, Bandit
├── Dockerfile             # Backend app container
├── docker-compose.yml     # postgres:16-alpine, redis:7-alpine, qdrant:v1.17.0
├── docker-compose.full.yml  # Full stack (backend + dashboard + postgres + redis + qdrant)
├── .env.docker            # Docker-specific env template
├── .env.example           # LLM_API_KEY, SERPER_API_KEY, DB/Redis/Qdrant URLs
├── README.md              # Public documentation (badges, architecture, quick start)
├── USAGE.md               # Detailed usage guide (web + CLI + API reference)
├── data/                  # Runtime settings (app_settings.json, gitignored)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add a CLI command | `src/council/cli.py` | Typer `@app.command()` |
| Add a FastAPI route | `src/council/main.py` | Currently minimal — routes inline |
| Add a council agent | `src/council/agents/` + `src/council/skills/` | Node function + markdown cognitive manual |
| Add a data source | `src/council/collectors/` | Extend `BaseCollector[T]`, wire in `pipeline.py` |
| Change agent behavior | `src/council/skills/*.md` | No code changes — runtime-loaded markdown |
| Change LLM models | `src/council/llm/client.py` | Configure via env vars or Settings page |
| Add a database table | `src/council/models/db.py` | SQLAlchemy + `alembic revision --autogenerate` |
| Fix a migration | `alembic/versions/` + `alembic` CLI |
| Debug the pipeline | `src/council/pipeline.py:run_analysis()` | Wires all layers sequentially |
| Debug an agent | Test standalone: `PYTHONPATH=src uv run python -c "..."` | See README for examples |
| Change dashboard | `dashboard/src/app/` | Next.js App Router pages and components |
| Change Settings page | `dashboard/src/app/settings/page.tsx` | Per-agent model/provider config UI |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `run_analysis()` | async fn | `pipeline.py:21` | Main orchestrator — collect → embed → council → debate → write |
| `compile_council_graph()` | fn | `agents/council_graph.py` | Builds LangGraph StateGraph with parallel agents + debate loop |
| `Settings` | class | `config.py:7` | Pydantic v2 settings from `.env`, all fields optional with defaults |
| `AsyncLLMClient` | class | `llm/client.py` | OpenAI-compatible async client with retry and cost tracking |
| `BaseCollector[T]` | abstract class | `collectors/base.py` | Generic async data collector interface (`Python 3.12+ syntax`) |
| `CouncilState` | TypedDict | `agents/state.py` | LangGraph state with `Annotated[... operator.add]` reducers (crawl_results, enabled_sources) |
| `CouncilMemoryManager` | class | `memory/mempalace.py` | In-memory verbatim storage + semantic search (Phase 4: → MCP) |
| `detect_divergence()` | async fn | `debate/divergence.py` | LLM-based disagreement finder between agent outputs |
| `calculate_confidence_score()` | fn | `debate/confidence.py` | Master plan formula: base + diversity + recency − divergence_penalty |
| `AnalysisReport` | class | `models/report.py` | Final structured report: risks, assumptions, SWOT, debate summary, addendum |

## CONVENTIONS

- **`from __future__ import annotations`** on every file
- **Python 3.12+ type params**: `BaseCollector[T]`, not `Generic[T]`
- **Pydantic v2 strict**: `model_config = ConfigDict(strict=True)` on all models
- **`str | None`**, not `Optional[str]`
- **Async everywhere**: `async def` for all I/O functions
- **Double quotes**, 100-char line limit (Ruff enforced)
- **`snake_case`** files/functions, `SCREAMING_SNAKE` module constants
- **Loguru only**: `from council.logging_config import logger` (never stdlib `logging`)
- **Trace IDs**: `get_trace_id()` / `set_trace_id()` via `contextvars`
- **No `aiohttp`**: use `httpx.AsyncClient`
- **Pytest class-based**: `class TestComponent:` with `test_*` methods
- **`unittest.mock.AsyncMock`** for mocks (not `pytest-mock`)
- **Patch at call site**: `@patch("council.pipeline.ClassName")`, not `@patch("council.module.ClassName")`

## ANTI-PATTERNS (THIS PROJECT)

- **Never commit `.env`** — use `.env.example` as template
- **Never delete failing tests** — fix code, not tests
- **Never use `as any`, `@ts-ignore`, `# type: ignore`** — fix types
- **Never use stdlib `logging`** — Loguru only
- **Devil's Advocate output must never contain**: "with the right team", "promising concept",
  "there is potential if...", any encouraging closing sentence (enforced in `check_forbidden_phrases`)
- **Phase 4 TODO markers** in `memory/mempalace.py` — do NOT remove, they track planned MCP migration
- **Singletons ok**: `get_llm_client()`, `get_settings()`, `get_qdrant_client()` — module-level pattern

## UNIQUE STYLES

- **Skills as markdown**: `src/council/skills/` contains `.md` files loaded into agent system prompts at runtime.
  Not a Python package — no `__init__.py`. Changes take effect without code changes.
- **Phase migration tags**: `# TODO Phase 4: Swap to MCP` markers in `memory/mempalace.py`
- **OpenAI-compatible only**: Configure any OpenAI-compatible endpoint via env vars or Settings page
- **Prompt-based divergence**: Same model for both agents, divergence from
  adversarial system prompts, not different model providers
## COMMANDS

```bash
# Run analysis
python -m council analyze "your startup idea"

# Tests
uv run pytest tests/ -v              # All tests (46)
uv run pytest tests/ -v -m unit     # Unit only

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# DB migrations
docker compose up -d postgres       # Start PostgreSQL
uv run alembic upgrade head         # Apply all migrations

# Docker services
docker compose up -d                # PostgreSQL + Redis + Qdrant

# Dev server
PYTHONPATH=src uvicorn council.main:app --port 8000

# Standalone component test
PYTHONPATH=src uv run python -c "
from council.collectors.reddit import RedditCollector
import asyncio
async def main():
    posts = await RedditCollector().collect('your topic', max_results=5)
    print(posts)
asyncio.run(main())
"
```

## NOTES

- OpenAI-compatible endpoints may rate-limit. Retry logic handles 429s.
- Qdrant v1.17+ uses `query_points()` not `search()` — the wrapper handles this.
- MemPalace is in-memory dict in Phase 1. Cross-process persistence requires Phase 4 MCP swap.
- Confidence score = 0 with single data source + high divergence is **correct behavior** — means "need more data."
- GitHub Actions CI not yet configured. Dockerfile exists for backend; full stack via docker-compose.full.yml.
- No `mypy`/`pyright` type checking configured. Ruff catches most issues.
- Alembic `hooks = ruff` is commented out — add if you want auto-format migrations.
