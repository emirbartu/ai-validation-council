from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from council.config import get_settings_manager, settings
from council.logging_config import setup_logging

try:
    from council.models.db import async_engine
except Exception as exc:
    logger.warning(f"DB engine unavailable: {exc}")
    async_engine = None

try:
    from council.knowledge.qdrant_client import get_qdrant_client
except Exception as exc:
    logger.warning(f"Qdrant client unavailable: {exc}")
    get_qdrant_client = None

try:
    from redis.asyncio import from_url as redis_from_url
except Exception as exc:
    logger.warning(f"Redis client unavailable: {exc}")
    redis_from_url = None


async def check_db_health() -> bool:
    if async_engine is None or settings.database_url is None:
        return False
    try:
        async with async_engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


async def check_qdrant_health() -> bool:
    if get_qdrant_client is None:
        return False
    try:
        client = await get_qdrant_client()
        try:
            await client._client.http.healthz.healthz()
        except AttributeError:
            await client._client.get_collections()
        return True
    except Exception:
        return False


async def check_redis_health() -> bool:
    if redis_from_url is None or settings.redis_url is None:
        return False
    try:
        client = redis_from_url(settings.redis_url)
        await client.ping()
        await client.close()
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(level=settings.log_level, json=False)
    logger.info("Council API starting")

    if async_engine is not None and settings.database_url is not None:
        try:
            logger.info("Initialising DB engine")
        except Exception as exc:
            logger.warning(f"DB initialisation skipped: {exc}")
    else:
        logger.warning("DATABASE_URL not set or DB engine unavailable – skipping DB init")

    if get_qdrant_client is not None:
        try:
            qdrant = await get_qdrant_client()
            await qdrant.ensure_collection("shallow_data")
            logger.info("Qdrant collection ensured")
        except Exception as exc:
            logger.warning(f"Qdrant initialisation skipped: {exc}")
    else:
        logger.warning("Qdrant client unavailable – skipping Qdrant init")

    yield

    logger.info("Council API shutting down")

    if async_engine is not None:
        try:
            await async_engine.dispose()
            logger.info("DB engine closed")
        except Exception as exc:
            logger.warning(f"DB engine close failed: {exc}")

    if get_qdrant_client is not None:
        try:
            qdrant = await get_qdrant_client()
            await qdrant._client.close()
            logger.info("Qdrant client closed")
        except Exception as exc:
            logger.warning(f"Qdrant client close failed: {exc}")


app = FastAPI(
    title="AI Validation Council API",
    version="0.1.0",
    lifespan=lifespan,
)

allow_origins = ["*"] if settings.environment.lower() == "development" else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "AI Validation Council API",
        "docs": "/docs",
    }


class AnalyzeRequest(BaseModel):
    idea: str
    max_results: int = 10
    profile: str = "full"


class SettingsUpdate(BaseModel):
    enable_reddit: bool | None = None
    enable_hackernews: bool | None = None
    enable_crawl4ai: bool | None = None
    market_analyst_model: str | None = None
    market_analyst_base_url: str | None = None
    market_analyst_api_key: str | None = None
    devils_advocate_model: str | None = None
    devils_advocate_base_url: str | None = None
    devils_advocate_api_key: str | None = None
    divergence_model: str | None = None
    divergence_base_url: str | None = None
    divergence_api_key: str | None = None
    report_model: str | None = None
    report_base_url: str | None = None
    report_api_key: str | None = None
    market_analyst_provider: str | None = None
    devils_advocate_provider: str | None = None
    divergence_provider: str | None = None
    report_provider: str | None = None
    log_level: str | None = None


@app.post("/api/analyze")
async def api_analyze(req: AnalyzeRequest):
    from council.pipeline import run_analysis

    result = await run_analysis(req.idea, profile=req.profile)
    report = result.get("report") or {}
    return {
        "query": req.idea,
        "report": report,
        "agent_outputs": [
            {"role": o.get("role", "?"), "content": o.get("content", ""), "kill_shots": o.get("kill_shots", [])}
            for o in result.get("agent_outputs", [])
        ],
        "divergence_points": result.get("divergence_points", []),
        "confidence_score": result.get("confidence_score", 0),
        "rounds": result.get("round", 0),
    }


@app.get("/api/history")
async def api_history(limit: int = 10):
    from council.memory.writeback import list_analyses

    analyses = list_analyses(limit)
    return {"analyses": analyses}


@app.get("/api/history/{analysis_id}")
async def api_history_detail(analysis_id: str):
    from council.memory.writeback import get_analysis

    result = get_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@app.get("/api/settings")
async def api_get_settings():
    manager = get_settings_manager()
    return {
        "settings": manager.mask_secrets(),
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }


@app.put("/api/settings")
async def api_update_settings(update: SettingsUpdate):
    manager = get_settings_manager()
    changed = manager.apply_update(update.model_dump(exclude_none=True))
    return {
        "settings": manager.mask_secrets(),
        "updated_fields": list(changed.keys()),
    }


class ModelTestRequest(BaseModel):
    model: str
    base_url: str | None = None
    api_key: str | None = None


@app.post("/api/settings/test-model")
async def api_test_model(req: ModelTestRequest):
    from council.llm.client import get_llm_client

    try:
        client = get_llm_client()
        response = await client.achat(
            model_key=req.model,
            system_prompt="You are a helpful assistant.",
            user_prompt="Reply with exactly: pong",
            api_key_override=req.api_key,
            base_url_override=req.base_url,
        )
        return {"success": True, "response": response.strip()[:100]}
    except Exception as exc:
        return {"success": False, "error": str(exc)[:500]}


@app.get("/health")
async def health() -> dict[str, str | dict[str, str]]:
    db_ok = "ok" if await check_db_health() else "error"
    qdrant_ok = "ok" if await check_qdrant_health() else "error"
    redis_ok = "ok" if await check_redis_health() else "error"

    return {
        "status": "healthy",
        "version": "0.1.0",
        "services": {
            "db": db_ok,
            "qdrant": qdrant_ok,
            "redis": redis_ok,
        },
    }
