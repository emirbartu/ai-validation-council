# 🏛️ AI Validation Council

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1-orange)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue)](LICENSE)
[![React Doctor](https://img.shields.io/badge/react--doctor-96%25-success)](https://react.doctor)

Multi-agent AI council that validates startup ideas through adversarial debate
with real-time Reddit & Hacker News data collection.
> ⚠️ **Non-Commercial Use Only.** This software is licensed under the PolyForm Noncommercial License. Commercial use, including use within revenue-generating products or services, is prohibited without a separate commercial license from the copyright holder.

---

## Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Reddit/HN       │───▶│  Qdrant           │───▶│  Market Analyst     │
│  Collectors      │    │  (embeddings)     │    │  (TAM/SAM/SOM)      │
└──────────────────┘    └──────────────────┘    └──────────┬──────────┘
                                                           │
                                                   ┌───────▼──────────┐
                                                   │  Debate Loop      │
                                                   │  (LangGraph)      │
                                                   └───────┬──────────┘
                                                           │
┌──────────────────┐    ┌──────────────────┐    ┌──────────▼──────────┐
│  Dashboard       │◀───│  FastAPI          │◀───│  Devil's Advocate  │
│  (Next.js)       │    │  /api/analyze     │    │  (Kill Shots)      │
└──────────────────┘    └──────────────────┘    └─────────────────────┘
```

## Quick Start

### Option 1: Docker (recommended)

```bash
git clone <repo-url> && cd council
cp .env.example .env
# Edit .env with your LLM API key (any OpenAI-compatible provider)

docker compose up -d          # PostgreSQL, Redis, Qdrant
PYTHONPATH=src uv run uvicorn council.main:app --port 8000
```

Then in a separate terminal:
```bash
cd dashboard && bun install && bun run dev
# Open http://localhost:3000
```

### Option 2: uv + bun (manual)

```bash
git clone <repo-url> && cd council
uv sync
cp .env.example .env
# Edit .env with your LLM API key

PYTHONPATH=src uv run python -m council analyze "your startup idea"
```

The app falls back to in-memory storage (MemPalace) when database services are unavailable.

## Features

- **Adversarial debate** — Two agents with opposing system prompts find where they disagree, not where they agree
- **Anti-sycophancy enforcement** — Hardcoded forbidden phrases in the Devil's Advocate; any encouragement is rejected and retried
- **Confidence scoring** — Transparent formula: data volume + source diversity + recency minus divergence penalty
- **SWOT generation** — Each analysis includes strengths, weaknesses, opportunities, and threats grounded in collected data
- **Real-time data** — Reddit (via Serper API) and HackerNews (via Algolia API) collected fresh per analysis
- **Per-agent model config** — Each agent runs on independently configurable models and providers via the Settings page
- **CLI + Web UI** — Terminal-first with a Next.js dashboard for browsing history and tweaking configuration
- **MemPalace memory** — Agents remember verbatim outputs from previous analyses; cross-session context accumulates

## What Makes This Different

Most "AI startup validators" are thin wrappers around a single system prompt. This system is structurally different:

| Pattern | Generic AI Wrapper | Validation Council |
|---|---|---|
| Analysis surface | Single prompt → single output | Multi-agent debate with divergence detection |
| Transparency | Black-box score with no explanation | Confidence formula is public, each component visible |
| Data grounding | Limited and basic web search | Real Reddit/HN posts collected per query, cited in output |
| Sycophancy | LLM agrees by default | Devil's Advocate forbidden from encouragement |
| Model flexibility | Fixed model, one size | Per-agent model/provider configuration at runtime |
| Memory | Stateless per query | MemPalace persists agent reasoning across sessions |

The core insight: disagreement is the signal. Two agents that agree on everything haven't found anything interesting. Two agents that fight about specific assumptions, data interpretations, or market risks are producing actual analytical value.

## How It Works

### The Council Process

When you run `python -m council analyze "your idea"`, five layers execute in sequence:

1. **Data Collection** — Reddit posts and HN stories are collected in parallel for the target market/idea
2. **Knowledge Embedding** — Text is chunked, embedded via `sentence-transformers`, and indexed in Qdrant for semantic retrieval
3. **LLM Council** — Two agents run in parallel inside a LangGraph state machine:
   - **Market Analyst** — Estimates TAM/SAM/SOM, finds growth trends, pricing signals, and demand evidence. Every claim must cite a source or label itself as an assumption.
   - **Devil's Advocate** — Finds structural failure modes (kill shots). Required to be "right about failure," not balanced. Output with forbidden phrases like "this is promising" is rejected and retried.
4. **Debate Engine** — A Divergence Detector reads both agent outputs and identifies specific disagreements with: topic, Position A, Position B, and what data would resolve it.
5. **Write-back** — Agent outputs, divergence points, and confidence scores are stored in MemPalace for future sessions.

### Confidence Score Formula

```
confidence = data_volume_factor(0–40)
           + source_diversity(0–20)
           + data_recency(0–20)
           − divergence_penalty(−5 per disagreement)

Final score clamped: 0–100
```

**Score interpretation:**

| Range | Meaning |
|---|---|
| 80–100 | High confidence — strong data, minimal disagreement |
| 60–79 | Moderate confidence — reasonable data, some divergent views |
| 40–59 | Low confidence — limited data or significant disagreement |
| 20–39 | Very low confidence — insufficient data or major disagreements |
| 0–19 | Unreliable — critical data or consensus gaps. More research required.

A score of 30 with 6 divergence points is honest. Dressing up uncertainty as "moderate confidence" is manipulation. The system tells you what it doesn't know.

## Usage

### CLI

```bash
# Analyze a startup idea
PYTHONPATH=src uv run python -m council analyze "your startup idea"

# The output includes:
#   - Collected data summary (Reddit posts, HN stories)
#   - Market Analyst report (TAM/SAM/SOM, growth, pricing)
#   - Devil's Advocate report (verdict, kill shots, fatal assumption)
#   - Divergence report (specific disagreements between agents)
#   - Confidence score with component breakdown
```

### Web Dashboard

Open `http://localhost:3000` after starting both backend and frontend.

| Page | URL | Description |
|---|---|---|
| Home | `/` | Enter a startup idea, trigger analysis, view results with confidence gauge |
| History | `/history` | Browse past analyses with scores and divergence counts |
| Analysis | `/analysis/[id]` | Deep-dive into a single analysis: agent outputs, divergence list, score breakdown |
| Settings | `/settings` | Configure per-agent models, providers, API keys, data source toggles |

The Settings page persists configuration to `data/app_settings.json`. Each agent (Market Analyst, Devil's Advocate, Divergence Detector) gets its own model, base URL, and provider. A "Test Connection" button validates your setup.

### API Reference

Start the backend and open `http://localhost:8000/docs` for interactive Swagger docs. Available endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analyze` | Run full council analysis. Body: `{"idea": "..."}` |
| `GET` | `/api/history?limit=N` | List past analyses |
| `GET` | `/api/history/{id}` | Get full analysis detail |
| `GET` | `/api/settings` | Read current config (secrets masked) |
| `PUT` | `/api/settings` | Partial update to runtime settings |
| `POST` | `/api/settings/test-model` | Test a model connection with custom config |
| `GET` | `/health` | Service health check |

## Configuration

Copy the template and fill in your keys:

```bash
cp .env.example .env
```

### Critical Variables

```bash
# Required — any OpenAI-compatible provider. Set base_url and key.
LLM_API_KEY=your-key-here
# Optional — get one at https://serper.dev (free tier: 2,500 queries/month)
# Without this, only HN data is collected
SERPER_API_KEY=your-serper-key
```

### Full Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_API_KEY` | Yes | — | LLM API key for your chosen provider |
| `SERPER_API_KEY` | No | — | Google search API for Reddit data collection |
| `DATABASE_URL` | No | `postgresql+asyncpg://council:council@localhost:5432/council` | Async PostgreSQL connection |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis for caching and task queuing |
| `QDRANT_URL` | No | `http://localhost:6333` | Qdrant vector database for semantic search |
| `QDRANT_API_KEY` | No | — | Qdrant cloud API key (only for hosted Qdrant) |
| `LLM_DAILY_LIMIT` | No | `50.0` | Daily LLM spending limit in USD |
| `MAX_ANALYSES_PER_USER_PER_DAY` | No | `5` | Rate limit for API users |
| `MAX_CONCURRENT_ANALYSES` | No | `3` | Max simultaneous analysis jobs |
| `ENVIRONMENT` | No | `development` | `development` or `production` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Docker

The project includes infrastructure services — PostgreSQL (with Alembic migrations), Redis, and Qdrant. The application itself runs outside Docker during development.

```bash
# Start all infrastructure
docker compose up -d

# Check service health
docker ps --filter "name=council-"

# Run DB migrations
uv run alembic upgrade head

# Stop everything
docker compose down
```

Services:

| Service | Image | Port | Health Check |
|---|---|---|---|
| PostgreSQL | `postgres:16-alpine` | 5432 | `pg_isready` |
| Redis | `redis:7-alpine` | 6379 | `redis-cli ping` |
| Qdrant | `qdrant/qdrant:v1.17.0` | 6333 | `/healthz` |

There is no application Dockerfile yet — the app runs via `uv run` and `bun run dev` during development. Application containerization is tracked for Phase 4.

## Development

### Setup

```bash
git clone <repo-url> && cd council
uv sync --group dev
cp .env.example .env
# Edit .env with your LLM API key
```

### Tests

```bash
uv run pytest tests/ -v              # 46 tests (all)
uv run pytest tests/ -v -m unit     # Unit tests only
uv run pytest tests/ -v -m integration  # Integration tests (requires Docker)
```

### Linting

```bash
uv run ruff check src/ tests/       # Lint
uv run ruff format src/ tests/      # Format
```

### Running Components Standalone

```bash
# Test the LLM client
PYTHONPATH=src uv run python -c "
import asyncio
from council.llm.client import get_llm_client
async def main():
    client = get_llm_client()
    print(await client.achat('gpt-4o-mini', 'Be helpful.', 'Say hi.'))
asyncio.run(main())
"

# Test the Reddit collector
PYTHONPATH=src uv run python -c "
import asyncio
from council.collectors.reddit import RedditCollector
async def main():
    r = RedditCollector()
    posts = await r.collect('AI startups', max_results=3)
    for p in posts: print(f'r/{p.subreddit}: {p.title}')
asyncio.run(main())
"
```

### Project Conventions

- Python 3.12+ with `from __future__ import annotations` everywhere
- UV package manager, Ruff linter/formatter, pytest
- Async everywhere: `httpx.AsyncClient`, `SQLAlchemy[asyncio]`, `LangGraph ainvoke`
- Pydantic v2 with `model_config = ConfigDict(strict=True)` on all models
- `str | None` instead of `Optional[str]`
- Loguru only — never stdlib `logging`
- `unittest.mock.AsyncMock` for mocks, patching at the call site
- No `aiohttp` — `httpx.AsyncClient` only

## Known Limitations

- **Reddit data bias** — Demographics skew male, 20–35, Western, technical. Strong for SaaS and developer tools. Weak for healthcare, logistics, agriculture, non-English markets.
- **Rate limits** — Some LLM providers may return 429s. Retry logic handles this but analyses are slower during rate-limit windows.
- **Confidence = 0 with single source is correct** — Per the formula, this means "collect more data," not "your idea is bad."
- **No Serper key = no Reddit data** — HN-only analysis works but is less rich. Get a Serper key for full coverage.
- **Phase 1 memory is in-process** — MemPalace persistence is in-memory. Cross-restart persistence is Phase 4.
- **Single-round debate on default config** — Architecture supports 3 rounds but defaults to 1 to avoid rate limits.
- **No CI/CD yet** — GitHub Actions and application Dockerfiles are tracked for Phase 4.

## Roadmap

| Phase | Status | Scope |
|---|---|---|
| 1 — Core Skeleton | ✅ Complete | CLI, 2 agents, Reddit/HN collectors, divergence detection, confidence scoring, MemPalace memory |
| 2 — Full Council | 🔜 Planned | ICP Specialist, Competitive Intel agent, multi-round debate |
| 3 — Simulation + UI | 🔜 Planned | Monte Carlo scenarios, GTM simulations, SSE streaming from backend to dashboard |
| 4 — Deploy + Polish | 🔜 Planned | PDF report generation, user accounts, Railway deployment, cost dashboard, CI/CD |

## License

PolyForm Noncommercial 1.0.0 — see [LICENSE](LICENSE) for details. Commercial use prohibited.
