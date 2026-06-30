"""End-to-end analysis pipeline orchestrator.

Wires together data collection → Qdrant ingestion → LLM council → debate
→ confidence score → MemPalace write-back → formatted output.
"""

from __future__ import annotations

import asyncio
from typing import Any

from council.agents.council_graph import compile_council_graph
from council.agents.state import CouncilState
from council.collectors.hackernews import HNCollector
from council.collectors.reddit import RedditCollector
from council.config import get_settings
from council.knowledge.embeddings import EmbeddingPipeline
from council.logging_config import get_trace_id, logger, set_trace_id
from council.memory.writeback import store_analysis_results
from council.models.data import CollectedData


async def run_analysis(query: str, profile: str = "full") -> dict[str, Any]:
    trace_id = get_trace_id()
    if not trace_id:
        import uuid

        trace_id = str(uuid.uuid4())[:8]
        set_trace_id(trace_id)

    logger.info("pipeline_start query={} trace_id={}", query, trace_id)

    collected = await _collect_data(query)
    logger.info(
        "data_collected reddit={} hn={} crawl={}",
        len(collected.reddit_posts),
        len(collected.hn_stories),
        len(collected.crawl_results),
    )

    total_chunks = 0
    if collected.reddit_posts or collected.hn_stories or collected.crawl_results:
        try:
            pipeline = EmbeddingPipeline()
            ingest_result = await pipeline.ingest_collected_data(collected)
            logger.info("ingest_complete result={}", ingest_result)
            total_chunks = ingest_result.get("total", 0)
        except Exception as exc:
            logger.warning("ingest_skipped reason=qdrant_unavailable error={}", exc)

    graph = compile_council_graph()

    enabled_sources = []
    if collected.reddit_posts:
        enabled_sources.append("reddit")
    if collected.hn_stories:
        enabled_sources.append("hackernews")
    if collected.crawl_results:
        enabled_sources.append("crawl4ai")

    initial_state: CouncilState = {
        "query": query,
        "reddit_posts": [_post_to_dict(p) for p in collected.reddit_posts],
        "hn_stories": [_post_to_dict(s) for s in collected.hn_stories],
        "crawl_results": [_post_to_dict(r) for r in collected.crawl_results],
        "enabled_sources": enabled_sources,
        "agent_outputs": [],
        "divergence_points": [],
        "divergence_status": None,
        "confidence_score": 0.0,
        "round": 0,
        "error": None,
        "chunk_count": total_chunks,
        "counterfactual_triggered": False,
        "profile": profile,
    }

    result = await graph.ainvoke(initial_state)
    logger.info("graph_complete round={}", result.get("round", 0))

    await store_analysis_results(
        query=query,
        agent_outputs=result.get("agent_outputs", []),
        divergence_points=result.get("divergence_points", []),
        divergence_status=result.get("divergence_status", "parsed"),
        confidence_score=result.get("confidence_score", 0.0),
        report=result.get("report", {}),
    )

    return dict(result)


async def _collect_data(query: str) -> CollectedData:
    settings = get_settings()
    enable_reddit = settings.enable_reddit
    enable_hackernews = settings.enable_hackernews
    enable_crawl4ai = settings.enable_crawl4ai

    async def _collect_reddit() -> list[Any]:
        if not enable_reddit:
            return []
        reddit = RedditCollector()
        try:
            return await reddit.collect(query, max_results=10)
        except Exception as exc:
            logger.warning("reddit_collection_failed error={}", exc)
            return []

    async def _collect_hn() -> list[Any]:
        if not enable_hackernews:
            return []
        hn = HNCollector()
        try:
            return await hn.collect(query, max_results=10)
        except Exception as exc:
            logger.warning("hn_collection_failed error={}", exc)
            return []

    async def _collect_crawl() -> list[Any]:
        if not enable_crawl4ai:
            return []
        try:
            from council.collectors.crawl4ai import Crawl4AICollector

            collector = Crawl4AICollector()
            await collector.start()
            try:
                return await collector.collect(query, max_results=5)
            finally:
                await collector.close()
        except Exception as exc:
            logger.warning("crawl4ai_collection_failed error={}", exc)
            return []

    reddit_posts, hn_stories, crawl_results = await asyncio.gather(
        _collect_reddit(), _collect_hn(), _collect_crawl()
    )

    return CollectedData(
        reddit_posts=reddit_posts,
        hn_stories=hn_stories,
        crawl_results=crawl_results,
    )


def _post_to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, dict):
        return obj
    return {}
