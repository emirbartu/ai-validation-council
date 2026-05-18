"""MemPalace write-back module for persisting agent analyses."""

from __future__ import annotations

from typing import Any

from council.logging_config import logger
from council.memory.mempalace import CouncilMemoryManager

_memory_manager: CouncilMemoryManager | None = None


def _get_memory() -> CouncilMemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = CouncilMemoryManager()
        _memory_manager.ensure_wings()
    return _memory_manager


async def store_analysis_results(
    query: str,
    agent_outputs: list[dict[str, Any]],
    divergence_points: list[dict[str, Any]],
    confidence_score: float,
    report: dict[str, Any] | None = None,
) -> str:
    memory = _get_memory()
    import uuid as _uuid

    analysis_id = str(_uuid.uuid4())[:8]

    for output in agent_outputs:
        role = output.get("role", "unknown")
        agent_name = role
        memory.store_agent_output(agent_name, analysis_id, output)
        logger.info("mempalace_stored agent={} analysis_id={}", agent_name, analysis_id)

    for agent_name in ["market_analyst", "devils_advocate"]:
        memory.store_diary_entry(
            agent_name,
            f"ANALYSIS:{analysis_id}|query:{query[:80]}|"
            f"divergences:{len(divergence_points)}|confidence:{confidence_score}",
        )

    if report:
        import json as _json
        memory.store_diary_entry(
            "council",
            f"REPORT:{analysis_id}|{_json.dumps(report)}",
        )
        logger.info("report_stored analysis_id={}", analysis_id)

    return analysis_id


def recall_agent_context(agent_name: str, query: str | None = None) -> list[dict[str, Any]]:
    memory = _get_memory()
    if query:
        return memory.recall_past_analysis(agent_name, query=query, limit=3)
    diary = memory.read_recent_diary(agent_name, n_entries=5)
    return diary


def list_analyses(limit: int = 10) -> list[dict[str, Any]]:
    """Return a list of recent analysis summaries parsed from agent diaries."""
    memory = _get_memory()
    analyses: dict[str, dict[str, Any]] = {}

    for agent_name in ["market_analyst", "devils_advocate"]:
        entries = memory.read_recent_diary(agent_name, n_entries=limit * 2)
        for entry in entries:
            text = entry.get("entry", "")
            if not text.startswith("ANALYSIS:"):
                continue

            parts = text.split("|")
            if len(parts) < 4:
                continue

            analysis_id = parts[0].replace("ANALYSIS:", "")
            query = parts[1].replace("query:", "")
            try:
                divergence_count = int(parts[2].replace("divergences:", ""))
                confidence = float(parts[3].replace("confidence:", ""))
            except ValueError:
                continue

            if analysis_id not in analyses:
                analyses[analysis_id] = {
                    "analysis_id": analysis_id,
                    "query": query,
                    "timestamp": entry.get("timestamp", ""),
                    "agent_count": 0,
                    "divergence_count": divergence_count,
                    "confidence": confidence,
                }

            analyses[analysis_id]["agent_count"] += 1

    result = sorted(analyses.values(), key=lambda x: x.get("timestamp", ""), reverse=True)
    return result[:limit]


def get_analysis(analysis_id: str) -> dict[str, Any]:
    """Return a full analysis by ID, including both agent outputs."""
    memory = _get_memory()

    ma_outputs = memory.recall_past_analysis("market_analyst", analysis_id=analysis_id)
    da_outputs = memory.recall_past_analysis("devils_advocate", analysis_id=analysis_id)

    query = ""
    divergence_count = 0
    confidence = 0.0
    timestamp = ""

    for agent_name in ["market_analyst", "devils_advocate"]:
        entries = memory.read_recent_diary(agent_name, n_entries=1000)
        for entry in entries:
            text = entry.get("entry", "")
            if not text.startswith(f"ANALYSIS:{analysis_id}|"):
                continue
            parts = text.split("|")
            if len(parts) < 4:
                continue
            query = parts[1].replace("query:", "")
            try:
                divergence_count = int(parts[2].replace("divergences:", ""))
                confidence = float(parts[3].replace("confidence:", ""))
                timestamp = entry.get("timestamp", "")
            except ValueError:
                continue
            break

    result: dict[str, Any] = {
        "analysis_id": analysis_id,
        "query": query,
        "timestamp": timestamp,
        "market_analyst": ma_outputs[0]["content"] if ma_outputs else {},
        "devils_advocate": da_outputs[0]["content"] if da_outputs else {},
        "divergence_count": divergence_count,
        "confidence": confidence,
    }

    council_entries = memory.read_recent_diary("council", n_entries=1000)
    import json as _json
    for entry in council_entries:
        text = entry.get("entry", "")
        if text.startswith(f"REPORT:{analysis_id}|"):
            try:
                report_data = _json.loads(text.split("|", 1)[1])
                result.update(report_data)
            except Exception:
                pass
            break

    return result
