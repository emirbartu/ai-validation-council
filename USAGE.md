# AI Validation Council — Usage Guide

Multi-agent AI council that validates startup ideas through adversarial debate with real-time Reddit/HN data.

---

## Three Ways To Run

Pick whichever matches your setup:

| # | Mode | Best for | Backend | Dashboard | Infra (db/redis/qdrant) |
|---|------|----------|---------|-----------|-------------------------|
| **1** | **No Docker** | Lightweight local dev, no daemon running | host terminal | host terminal | host terminal (postgres/redis/qdrant as local processes) |
| **2** | **Mixed** | Hot-reload Python + Next.js dev, infrastructure isolated | host terminal | host terminal | `docker compose` |
| **3** | **Full Docker** | Production parity, single `up` command, reproducible | container | container | `docker compose` |

All three use the same `.env` and produce the same `/api/analyze` results.

---

## 0. First-time setup (all options)

```bash
# 1. Clone and enter the repo
git clone <repo-url> council && cd council

# 2. Configure secrets
cp .env.example .env
# Edit .env — at minimum set:
#   LLM_API_KEY=sk-...
#   SERPER_API_KEY=...    (optional, for Reddit data)

# 3. (macOS only) install uv + bun
brew install uv bun
```

---

## Option 1 — No Docker (everything on the host)

Run every service locally on your laptop. Use this when you don't want Docker Desktop running, or when you're developing on a low-resource machine.

### 1.1 Install infrastructure natively

**macOS / Linux:**

```bash
# PostgreSQL
brew install postgresql@16
brew services start postgresql@16
createdb council          # or: psql -c 'CREATE DATABASE council;'

# Redis
brew install redis
brew services start redis

# Qdrant (binary install)
brew install qdrant
qdrant --version          # verify it runs
```

### 1.2 Configure `.env`

```bash
# .env — already points at localhost, no edits needed
DATABASE_URL=postgresql+asyncpg://council:council@localhost:5432/council
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
```

### 1.3 Run database migrations

```bash
uv sync
uv run alembic upgrade head
```

### 1.4 Start the backend (terminal 1)

```bash
PYTHONPATH=src uv run uvicorn council.main:app --port 8000 --reload
```

### 1.5 Start the dashboard (terminal 2)

```bash
cd dashboard
bun install
bun run dev
# Open http://localhost:3000
```

### 1.6 Stopping

```bash
# Ctrl+C in each terminal
# Stop services:
brew services stop postgresql@16 redis
```

---

## Option 2 — Mixed: Docker infra + host terminal apps

Best of both worlds. Database/Redis/Qdrant run in containers (one `docker compose up` for everything). Backend and dashboard run on the host with full hot-reload.

### 2.1 Start infrastructure

```bash
docker compose up -d        # postgres, redis, qdrant
```

Verify:
```bash
docker compose ps
# All three should show "healthy"
```

`.env` already points at `localhost:5432`, `localhost:6379`, `localhost:6333`, which is correct because the host binds to those ports.

### 2.2 Run database migrations

```bash
uv sync
uv run alembic upgrade head
```

### 2.3 Start the backend (terminal 1)

```bash
PYTHONPATH=src uv run uvicorn council.main:app --port 8000 --reload
```

### 2.4 Start the dashboard (terminal 2)

```bash
cd dashboard
bun install
bun run dev
# Open http://localhost:3000
```

### 2.5 Stopping

```bash
# Ctrl+C in terminals 1 & 2
docker compose down              # stop and remove containers
docker compose down -v           # also wipe volumes (DB data) — destructive
```

---

## Option 3 — Full Docker

Everything runs in containers. Single command to bring up the whole stack. The backend uses Gunicorn-free Uvicorn (1 worker) — for production scale, scale `backend` replicas and put a load balancer in front.

### 3.1 Build and start

```bash
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml up --build -d
```

This builds **two images** (backend + dashboard) and starts **five containers**:

- `council-postgres` — PostgreSQL 16
- `council-redis` — Redis 7 (append-only persistence)
- `council-qdrant` — Qdrant vector DB
- `council-backend` — Python FastAPI on port 8000
- `council-dashboard` — Next.js on port 3000

### 3.2 Verify

```bash
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml ps
# All five should show "healthy" within ~30s

curl http://localhost:8000/health
# {"status":"healthy","version":"0.1.0","services":{"db":"ok","qdrant":"ok","redis":"ok"}}

# Open dashboard:
open http://localhost:3000
```

### 3.3 Run database migrations

The container images don't run migrations on boot. One-shot:

```bash
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml run --rm backend \
  alembic upgrade head
```

(Migrations are not strictly required for the API to work — the app falls back to JSONL history when the DB is missing, but DB writes require schema.)

### 3.4 Logs

```bash
# Follow a single service
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml logs -f backend

# All services, last 200 lines
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml logs --tail 200
```

### 3.5 Stopping

```bash
# Stop + remove containers (data preserved in named volumes)
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml down

# Stop + remove containers AND volumes (DB wiped)
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml down -v

# Restart a single service after code change (rebuild image)
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml up --build -d backend
```

### 3.6 Production deployment

For a public deployment (not just dev), edit `docker-compose.full.yml`:

```yaml
dashboard:
  build:
    args:
      NEXT_PUBLIC_API_URL: https://api.yourdomain.com   # public URL
```

Then run **without** the override file (no host port forwards):

```bash
docker compose -f docker-compose.full.yml up -d
```

Put a reverse proxy (Traefik, Caddy, Nginx) in front of ports 3000 and 8000.

---

## Verifying a real analysis

After starting in any mode, run:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"idea": "AI dental practice management software"}'
```

You'll get back a JSON report with the Market Analyst output, Devil's Advocate output, divergence points, and a confidence score.

The CLI also works once uv is set up:

```bash
PYTHONPATH=src uv run python -m council analyze "your startup idea"
```

---

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

---

## CLI reference

```bash
# Analyze a startup idea
PYTHONPATH=src uv run python -m council analyze "your startup idea"

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

---

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

---

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

---

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

---

## Troubleshooting

### `service "backend" has neither an image nor a build context specified: invalid compose project`

You're running `docker compose up -d` (no `-f`), but a leftover `docker-compose.override.yml` is auto-merging and referencing a `backend` service that doesn't exist in the infra-only base file. Fix:

```bash
# If you see a docker-compose.override.yml in the repo root, delete it.
# The repo uses docker-compose.dev.yml (opt-in via -f) instead.
rm docker-compose.override.yml    # if present

# Verify only the three intended compose files exist:
ls docker-compose*.yml
# docker-compose.dev.yml    docker-compose.full.yml    docker-compose.yml
```

This is fixed in the current repo (no `override.yml` ships), but if you forked an older revision, the override file may still be there.

### Docker build hangs for a long time

The first build downloads ~3 GB of Python wheels (torch + sentence-transformers + langgraph). Subsequent builds reuse the cache and finish in <30 s.

If you want to skip Playwright (saves another ~400 MB and ~2 min), the default Dockerfile already passes `INSTALL_PLAYWRIGHT=0`.

### Backend health says `db: error`

The app falls back to in-memory JSONL history when DB is unreachable. To get full DB-backed history:

1. Make sure PostgreSQL is running (Option 1: `brew services list`; Option 2/3: `docker compose ps`)
2. Run migrations: `uv run alembic upgrade head`
3. Restart the backend

### Dashboard says "Failed to fetch"

The dashboard's `NEXT_PUBLIC_API_URL` is baked into the JS bundle at build time. If you change it, rebuild the dashboard image (Option 3) or restart `bun run dev` (Option 1/2).

In Option 3 with the override file, `NEXT_PUBLIC_API_URL` is `http://localhost:8000` — make sure your host can reach the backend there.

### Port conflicts

- `5432` (Postgres) — change in `docker-compose.yml` / `docker-compose.full.yml` AND in your `.env`'s `DATABASE_URL`
- `6379` (Redis) — same pattern, `REDIS_URL`
- `6333` (Qdrant) — same pattern, `QDRANT_URL`
- `8000` (backend) — change in compose file `ports:`
- `3000` (dashboard) — change in compose file `ports:`

---

## Which option should I pick?

- **Just want to try it out?** → Option 1 (no Docker, no daemon).
- **Developing new features?** → Option 2 (Docker for infra, host terminal for hot-reload).
- **Deploying to a server?** → Option 3 (full Docker, single command).
- **CI/CD?** → Option 3 (build once, push image, run anywhere).