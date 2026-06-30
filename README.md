# 🏛️ AI Validation Council

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1-orange)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](Dockerfile)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue)](LICENSE)

Multi-agent AI council that validates startup ideas through adversarial debate with real-time Reddit & Hacker News data collection. Two LLM agents argue, a divergence detector scores their disagreements, a confidence formula tells you what the system doesn't know.

> ⚠️ **Non-Commercial Use Only.** PolyForm Noncommercial License — see [LICENSE](LICENSE). Commercial use prohibited.

---

## Documentation

| File | What's in it |
|---|---|
| **[README.md](README.md)** (this file) | What it is + how to run it |
| **[USAGE.md](USAGE.md)** | Step-by-step commands for all 3 run modes |
| **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** | Architecture, tech stack, conventions, Docker internals, known bugs — for developers digging into the code |

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

---

## Run in 3 ways

| # | Mode | Best for | Command |
|---|------|----------|---------|
| **1** | **No Docker** | Lightweight local dev, no daemon | everything on host terminal |
| **2** | **Mixed** | Hot-reload backend + dashboard | `docker compose up -d` for infra, host for apps |
| **3** | **Full Docker** | Production parity, single command | `docker compose -f docker-compose.full.yml -f docker-compose.dev.yml up --build -d` |

### Option 1 — No Docker (terminal only)

```bash
brew install postgresql@16 redis qdrant
brew services start postgresql@16 redis
qdrant &
uv sync && cp .env.example .env
uv run alembic upgrade head
PYTHONPATH=src uv run uvicorn council.main:app --port 8000 --reload   # terminal 1
```

```bash
cd dashboard && bun install && bun run dev                            # terminal 2
open http://localhost:3000
```

### Option 2 — Mixed (docker infra + host apps)

This brings up Postgres, Redis, and Qdrant in containers. Backend and dashboard run on the host with hot-reload.

```bash
docker compose up -d                              # postgres + redis + qdrant
# wait ~10s for healthchecks:
docker compose ps                                  # all 3 should say "healthy"
curl http://localhost:6333/healthz                 # → "healthz check passed"

uv sync && cp .env.example .env
uv run alembic upgrade head
PYTHONPATH=src uv run uvicorn council.main:app --port 8000 --reload   # terminal 1
```

```bash
cd dashboard && bun install && bun run dev                            # terminal 2
open http://localhost:3000
```

To stop the infra: `docker compose down` (keeps data volumes) or `docker compose down -v` (wipes data).

### Option 3 — Full Docker (single command)

Builds and runs everything — backend, dashboard, postgres, redis, qdrant — in containers. Single command to start, single command to stop.

```bash
cp .env.example .env       # set LLM_API_KEY + SERPER_API_KEY
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml up --build -d
# wait ~30s for the stack to come up:
docker compose -f docker-compose.full.yml -f docker-compose.dev.yml ps
# All 5 should say "healthy"
curl http://localhost:8000/health
# → {"status":"healthy","version":"0.1.0","services":{"db":"ok","qdrant":"ok","redis":"ok"}}
open http://localhost:3000
```

The `-f docker-compose.dev.yml` overlay exposes the backend and dashboard on host ports 8000 and 3000 (so your browser can reach them) and sets `NEXT_PUBLIC_API_URL=http://localhost:8000`. For a public deployment without host port forwards, run **without** the overlay:

```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com \
  docker compose -f docker-compose.full.yml up -d
```

To stop the full stack: `docker compose -f docker-compose.full.yml -f docker-compose.dev.yml down` (keeps volumes) or `down -v` (wipes everything).

That's it. 5 containers, persistent volumes, healthchecks, one `down` to stop.

Full step-by-step for every option, plus troubleshooting and production deployment: see **[USAGE.md](USAGE.md)**.

---

## Configure your LLM (no .env editing required)

The Settings page (`/settings` in the dashboard) lets you set the model name, base URL, and API key for each agent (Market Analyst, Devil's Advocate, Divergence Detector) and test the connection before saving. Persists to `data/app_settings.json` and overrides anything in `.env`.

You can also set `LLM_API_KEY` in `.env` as a fallback.

---

## Features

- **Adversarial debate** — Two agents with opposing system prompts find disagreements, not agreements.
- **Citation verification** — URLs/titles extracted from agent output are cross-checked against actually-collected Reddit/HN data. Hallucinated URLs score `verified: false` and don't inflate the confidence score.
- **Anti-sycophancy** — Forbidden phrases in Devil's Advocate (e.g. "this is promising") trigger a retry at lower temperature with a sterner prompt.
- **Parse-error transparency** — Divergence detector returns a status envelope (`parsed` / `parse_error` / `empty` / `insufficient_data`). No more silent `[]`.
- **Persistent history** — Every analysis written to `data/history.jsonl` before RAM; survives restarts.
- **Per-agent model config** — Each agent runs on its own model + provider, configurable at runtime via the dashboard.
- **Full Docker stack** — One `up` brings up backend, dashboard, postgres, redis, qdrant with healthchecks.

---

## The core insight

Disagreement is the signal. Two agents that agree on everything haven't found anything interesting. Two agents that fight about specific assumptions, data interpretations, or market risks are producing actual analytical value.

The confidence score rewards consensus and penalizes disagreement on purpose. A score of 30 with 6 divergence points is honest. Dressing up uncertainty as "moderate confidence" is manipulation. The system tells you what it doesn't know.

---

## For developers

- **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** — architecture deep-dive, tech stack with pinned versions, conventions (Pydantic strict, async-only, loguru-only, etc.), known bugs, Docker internals, roadmap, testing breakdown.

---

## License

PolyForm Noncommercial 1.0.0 — see [LICENSE](LICENSE). Commercial use prohibited.