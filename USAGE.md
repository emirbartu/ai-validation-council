# AI Validation Council — Usage Guide

Multi-agent AI council that validates startup ideas through adversarial debate with real-time Reddit/HN data.

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url> council && cd council
uv sync

# 2. Configure API keys (see below)
cp .env.example .env
# Edit .env with your keys

# 3. Install Playwright (for Crawl4AI — optional)
uv run playwright install chromium

# 4. Start the backend
PYTHONPATH=src uv run uvicorn council.main:app --port 8000

# 5. Start the dashboard (separate terminal)
cd dashboard && bun install && bun run dev
# Open http://localhost:3000
```

## Web Dashboard

Open `http://localhost:3000`. Three pages:

| Page | URL | What it does |
|------|-----|-------------|
| **Home** | `/` | Enter a startup idea, see analysis results with confidence score |
| **History** | `/history` | Browse past analyses with scores and divergence counts |
| **Settings** | `/settings` | Configure models, providers, and data sources |

### Settings Page

**Models & Providers tab** — Per-agent model configuration:
- **Market Analyst** — Researches TAM/SAM/SOM, growth trends, pricing signals
- **Devil's Advocate** — Finds structural failure modes (kill shots)
- **Divergence Detector** — Identifies disagreements between agents
Each agent card lets you set: model name, base URL, API key, and test the connection.

**Data Providers tab** — Toggle data sources on/off:
- **Reddit** (via Serper API — paid)
- **HackerNews** (via Algolia API — free)
- **Crawl4AI** (local browser crawler — free)

Settings are persisted to `data/app_settings.json` and survive restarts.

## CLI

```bash
# Analyze a startup idea
PYTHONPATH=src uv run python -m council analyze "your startup idea"

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze` | Run full council analysis. Body: `{"idea": "..."}` |
| `GET` | `/api/history?limit=N` | List past analyses |
| `GET` | `/api/history/{id}` | Get full analysis detail |
| `GET` | `/api/settings` | Read current config (secrets masked) |
| `PUT` | `/api/settings` | Update config (partial). Body: `{"enable_reddit": false, ...}` |
| `POST` | `/api/settings/test-model` | Test a model connection. Body: `{"model": "...", "base_url": "..."}` |
| `GET` | `/health` | Service health check |

## Key Files

### Secrets & Configuration

| File | Purpose | Contains |
|------|---------|----------|
| `.env` | **API keys and credentials** | `LLM_API_KEY`, `SERPER_API_KEY`, database URLs |
| `.env.example` | Template for `.env` | Same structure, no real keys |
| `data/app_settings.json` | Runtime settings (auto-generated) | Per-agent model config, data provider toggles — persisted across restarts |

### Core Pipeline

| File | Role |
|------|------|
| `src/council/pipeline.py` | End-to-end orchestrator: collect → embed → council → debate → write |
| `src/council/config.py` | Pydantic v2 Settings — all defaults, env vars, and runtime settings manager |
| `src/council/main.py` | FastAPI app — all API routes |
| `src/council/cli.py` | Typer CLI entry point |

### LLM Layer

| File | Role |
|------|------|
| `src/council/llm/client.py` | LLM client — OpenAI-compatible routing, retry, cost tracking |

### Agents

| File | Role |
|------|------|
| `src/council/agents/market_analyst.py` | Market Analyst node — TAM/SAM/SOM, growth, pricing, demand |
| `src/council/agents/devils_advocate.py` | Devil's Advocate node — kill shots, anti-sycophancy enforcement |
| `src/council/agents/council_graph.py` | LangGraph builder — parallel agent execution, debate loop |
| `src/council/skills/market_analyst.md` | Market Analyst cognitive manual (runtime-loaded) |
| `src/council/skills/devils_advocate.md` | Devil's Advocate cognitive manual (runtime-loaded) |

### Debate & Scoring

| File | Role |
|------|------|
| `src/council/debate/divergence.py` | LLM-based disagreement detector between agent outputs |
| `src/council/debate/confidence.py` | Confidence score v2 — sigmoid-based, non-linear divergence penalty |

### Data Collection

| File | Role |
|------|------|
| `src/council/collectors/reddit.py` | Reddit collector via Serper API |
| `src/council/collectors/hackernews.py` | HN collector via Algolia API |
| `src/council/collectors/crawl4ai.py` | Web crawler using Playwright (competitor pages) |

### Frontend

| File | Role |
|------|------|
| `dashboard/src/app/page.tsx` | Home page — idea input + analysis trigger |
| `dashboard/src/app/settings/page.tsx` | Settings page — model/provider/data provider config |
| `dashboard/src/app/history/page.tsx` | History page — past analyses table |
| `dashboard/src/app/analysis/[id]/page.tsx` | Analysis detail — agent outputs, confidence gauge, divergence list |
| `dashboard/src/lib/api.ts` | Single source of truth API client |

## Infrastructure (Optional)

```bash
# Start Docker services (PostgreSQL, Redis, Qdrant)
docker compose up -d

# Run DB migrations
uv run alembic upgrade head
```

The app works without Docker — it falls back to in-memory storage (MemPalace) when DB/Qdrant/Redis are unavailable.

## Environment Variables

See `.env.example` for the full list. The critical ones:

```bash
# Required for LLM calls
LLM_API_KEY=              # Your OpenAI-compatible API key
# Optional data sources
SERPER_API_KEY=              # For Reddit data collection (paid)

# Infrastructure (optional — app works without Docker)
DATABASE_URL=postgresql+asyncpg://council:council@localhost:5432/council
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
```

## Stopping

```bash
# Stop the backend
Ctrl+C in the backend terminal

# Stop the dashboard
Ctrl+C in the dashboard terminal

# Stop Docker services (if running)
docker compose down
```
