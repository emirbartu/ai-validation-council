"""Test persistent history storage (Module 2).

Spec:
- ``store_analysis_results()`` writes one JSONL line to ``data/history.jsonl``.
- ``list_analyses()`` reads from the same file and sorts desc by timestamp.
- ``get_analysis(id)`` returns full detail for a known ID.
- ``Divergence_status`` is included in every record.
"""

from __future__ import annotations

import json

import pytest

from council.memory import writeback


@pytest.fixture(autouse=True)
def isolated_history(tmp_path, monkeypatch):
    """Force ``writeback`` to read/write a tmp JSONL so we don't poison
    the real ``data/history.jsonl``."""
    test_file = tmp_path / "history.jsonl"
    monkeypatch.setattr(writeback, "HISTORY_FILE", test_file)
    monkeypatch.setattr(writeback, "DATA_DIR", tmp_path)
    return test_file


@pytest.mark.asyncio
async def test_store_writes_jsonl_record(isolated_history):
    await writeback.store_analysis_results(
        query="dental SaaS",
        agent_outputs=[{"role": "market_analyst", "content": "x"}],
        divergence_points=[{"topic": "pricing"}],
        divergence_status="parsed",
        confidence_score=42.0,
        report={"summary": "ok"},
    )

    assert isolated_history.exists()
    lines = isolated_history.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["query"] == "dental SaaS"
    assert record["confidence_score"] == 42.0
    assert record["divergence_status"] == "parsed"
    assert "id" in record
    assert "timestamp" in record


@pytest.mark.asyncio
async def test_list_analyses_returns_most_recent_first(isolated_history):
    for query in ["q1", "q2", "q3"]:
        await writeback.store_analysis_results(
            query=query,
            agent_outputs=[],
            divergence_points=[],
            divergence_status="parsed",
            confidence_score=1.0,
        )
    history = writeback.list_analyses(limit=10)
    assert len(history) == 3
    queries = [h["query"] for h in history]
    assert queries == ["q3", "q2", "q1"]


@pytest.mark.asyncio
async def test_list_analyses_includes_divergence_status(isolated_history):
    await writeback.store_analysis_results(
        query="q",
        agent_outputs=[],
        divergence_points=[],
        divergence_status="parse_error",
        confidence_score=0.0,
    )
    [summary] = writeback.list_analyses()
    assert summary["divergence_status"] == "parse_error"


@pytest.mark.asyncio
async def test_get_analysis_returns_detail(isolated_history):
    aid = await writeback.store_analysis_results(
        query="detail-q",
        agent_outputs=[
            {"role": "market_analyst", "content": "ma-content", "citations": []},
            {"role": "devils_advocate", "content": "da-content", "kill_shots": []},
        ],
        divergence_points=[{"topic": "x"}],
        divergence_status="empty",
        confidence_score=55.5,
        report={"hello": "world"},
    )
    detail = writeback.get_analysis(aid)
    assert detail["analysis_id"] == aid
    assert detail["query"] == "detail-q"
    assert detail["confidence"] == 55.5
    assert detail["divergence_status"] == "empty"
    assert detail["market_analyst"]["content"] == "ma-content"
    assert detail["devils_advocate"]["content"] == "da-content"
    assert detail["report"] == {"hello": "world"}


@pytest.mark.asyncio
async def test_get_analysis_unknown_id_returns_empty(isolated_history):
    assert writeback.get_analysis("does-not-exist") == {}


@pytest.mark.asyncio
async def test_data_dir_created_if_missing(tmp_path, monkeypatch):
    """If the data/ directory is absent, store_analysis_results should not
    raise. We point DATA_DIR at a fresh non-existent subdir."""
    new_dir = tmp_path / "fresh" / "nested"
    monkeypatch.setattr(writeback, "DATA_DIR", new_dir)
    monkeypatch.setattr(writeback, "HISTORY_FILE", new_dir / "history.jsonl")

    await writeback.store_analysis_results(
        query="q",
        agent_outputs=[],
        divergence_points=[],
        divergence_status="parsed",
        confidence_score=0.0,
    )

    assert writeback.HISTORY_FILE.exists()


@pytest.mark.asyncio
async def test_list_analyses_limit_respected(isolated_history):
    for i in range(5):
        await writeback.store_analysis_results(
            query=f"q{i}",
            agent_outputs=[],
            divergence_points=[],
            divergence_status="parsed",
            confidence_score=0.0,
        )
    assert len(writeback.list_analyses(limit=2)) == 2


@pytest.mark.asyncio
async def test_persistence_across_instances(isolated_history):
    """Simulate 'restart' — write, then re-import the module to confirm the
    file-backed reader sees the record."""
    aid = await writeback.store_analysis_results(
        query="persistence-test",
        agent_outputs=[{"role": "market_analyst", "content": "x"}],
        divergence_points=[],
        divergence_status="parsed",
        confidence_score=10.0,
    )

    # Force a fresh module state by clearing the singleton.
    writeback._memory_manager = None

    detail = writeback.get_analysis(aid)
    assert detail["analysis_id"] == aid
    assert detail["query"] == "persistence-test"
