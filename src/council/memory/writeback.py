"""JSONL write-back module for persisting agent analyses."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from council.logging_config import logger

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.jsonl"


def _append_history(record: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _load_history() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def store_analysis_results(
    query: str,
    agent_outputs: list[dict[str, Any]],
    divergence_points: list[dict[str, Any]],
    confidence_score: float,
    report: dict[str, Any] | None = None,
    divergence_status: str = "parsed",
) -> str:
    analysis_id = str(uuid.uuid4())[:8]

    record = {
        "id": analysis_id,
        "query": query,
        "timestamp": datetime.now(UTC).isoformat(),
        "agent_outputs": agent_outputs,
        "divergence_points": divergence_points,
        "divergence_status": divergence_status,
        "confidence_score": confidence_score,
        "report": report,
    }
    _append_history(record)
    logger.info(
        "history_saved analysis_id={} file={} divergence_status={}",
        analysis_id,
        HISTORY_FILE,
        divergence_status,
    )

    return analysis_id


def list_analyses(limit: int = 10) -> list[dict[str, Any]]:
    all_items = _load_history()
    sorted_items = sorted(all_items, key=lambda x: x.get("timestamp", ""), reverse=True)
    return [
        {
            "analysis_id": item["id"],
            "query": item["query"],
            "timestamp": item["timestamp"],
            "agent_count": len(item.get("agent_outputs", [])),
            "divergence_count": len(item.get("divergence_points", [])),
            "divergence_status": item.get("divergence_status", "parsed"),
            "confidence": item.get("confidence_score", 0),
        }
        for item in sorted_items[:limit]
    ]


def get_analysis(analysis_id: str) -> dict[str, Any]:
    for item in _load_history():
        if item.get("id") == analysis_id:
            agent_outputs = item.get("agent_outputs", [])
            ma = next((o for o in agent_outputs if o.get("role") == "market_analyst"), {})
            da = next((o for o in agent_outputs if o.get("role") == "devils_advocate"), {})
            return {
                "analysis_id": analysis_id,
                "query": item["query"],
                "timestamp": item["timestamp"],
                "market_analyst": ma,
                "devils_advocate": da,
                "divergence_count": len(item.get("divergence_points", [])),
                "divergence_status": item.get("divergence_status", "parsed"),
                "confidence": item.get("confidence_score", 0),
                "report": item.get("report"),
            }
    return {}
