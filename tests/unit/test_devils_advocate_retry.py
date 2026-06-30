"""Test Devil's Advocate anti-sycophancy enforcement + retry (Module 5).

Spec checks:
- Output containing "this is promising" → retry triggered at temp 0.3
- Final output does NOT contain the forbidden phrase
- Loguru logs contain ``devils_advocate_sycophancy_detected`` and retry markers
"""

from __future__ import annotations

import pytest

from council.agents import devils_advocate

SAMPLE_REDDIT = [
    {"id": "abc", "title": "AI dental CRM", "url": "https://reddit.com/r/Dentistry/comments/abc/"}
]
SAMPLE_HN = [
    {
        "id": 100,
        "title": "Show HN: dental SaaS",
        "url": "https://news.example.com/x",
        "by": "founder",
    }
]


FORBIDDEN_DRAFT = (
    "Kill Shot 1: Unit economics. CAC $500 vs ARPU $50. "
    "However, this is promising and worth considering for the right team."
)

CLEAN_DRAFT = (
    "Kill Shot 1: Unit economics. CAC $500 vs ARPU $50 — 10-month payback impossible. "
    "Kill Shot 2: Distribution. Industry sales cycle is 18 months; this team has 0 relationships. "
    "Kill Shot 3: Switching costs. Practices have used Dentrix for 15 years. 3% annual churn floor. "
    "THE FATAL ASSUMPTION: This idea requires dentists to abandon incumbent software with no measurable gain. "
    "Source: https://reddit.com/r/Dentistry/comments/abc/ — three dentists confirm zero switching intent."
)


def _make_state():
    return {
        "query": "dental SaaS",
        "reddit_posts": SAMPLE_REDDIT,
        "hn_stories": SAMPLE_HN,
        "round": 0,
    }


@pytest.mark.asyncio
async def test_sycophancy_triggers_retry(monkeypatch):
    """Forbid phrase present in first response → retry; second response is clean."""
    responses = [FORBIDDEN_DRAFT, CLEAN_DRAFT]

    async def fake_call(system_prompt, user_prompt, append_instruction=None, temperature=0.7):
        return responses.pop(0)

    monkeypatch.setattr(devils_advocate, "_call_devils_advocate", fake_call)

    state = _make_state()
    result = await devils_advocate.devils_advocate_node(state)
    outputs = result["agent_outputs"]
    assert len(outputs) == 1
    out = outputs[0]

    assert out["retry_attempted"] is True
    assert out["forbidden_check_passed"] is True
    assert "promising" not in out["content"].lower()
    assert "worth considering" not in out["content"].lower()


@pytest.mark.asyncio
async def test_sycophancy_log_marker_present(monkeypatch):
    import json

    from council.logging_config import logger

    captured: list[str] = []

    def sink(message: str) -> None:
        record = json.loads(message)
        captured.append(record["record"]["message"])

    handler_id = logger.add(sink, level="WARNING", serialize=True)
    try:
        responses = [FORBIDDEN_DRAFT, CLEAN_DRAFT]

        async def fake_call(system_prompt, user_prompt, append_instruction=None, temperature=0.7):
            return responses.pop(0)

        monkeypatch.setattr(devils_advocate, "_call_devils_advocate", fake_call)
        state = _make_state()
        await devils_advocate.devils_advocate_node(state)
    finally:
        logger.remove(handler_id)

    joined = " ".join(captured)
    assert "devils_advocate_sycophancy_detected" in joined
    assert "retry_attempt=1" in joined


@pytest.mark.asyncio
async def test_no_sycophancy_no_retry(monkeypatch):
    responses = [CLEAN_DRAFT]

    async def fake_call(system_prompt, user_prompt, append_instruction=None, temperature=0.7):
        return responses.pop(0)

    monkeypatch.setattr(devils_advocate, "_call_devils_advocate", fake_call)

    state = _make_state()
    result = await devils_advocate.devils_advocate_node(state)
    out = result["agent_outputs"][0]
    assert out["retry_attempted"] is False
    assert out["forbidden_check_passed"] is True


@pytest.mark.asyncio
async def test_retry_uses_temperature_three(monkeypatch):
    """Per spec, retry at temperature=0.3 (not 0.7)."""
    temps: list[float] = []

    async def fake_call(system_prompt, user_prompt, append_instruction=None, temperature=0.7):
        temps.append(temperature)
        return [FORBIDDEN_DRAFT, CLEAN_DRAFT][len(temps) - 1]

    monkeypatch.setattr(devils_advocate, "_call_devils_advocate", fake_call)
    state = _make_state()
    await devils_advocate.devils_advocate_node(state)
    assert temps[0] == 0.7
    assert temps[1] == 0.3


@pytest.mark.asyncio
async def test_sycophancy_persists_after_retry_logs_failure(monkeypatch):
    """If retry still has forbidden phrases, log a second warning."""
    import json

    from council.logging_config import logger

    captured: list[str] = []

    def sink(message: str) -> None:
        record = json.loads(message)
        captured.append(record["record"]["message"])

    handler_id = logger.add(sink, level="WARNING", serialize=True)
    try:
        responses = [FORBIDDEN_DRAFT, FORBIDDEN_DRAFT]

        async def fake_call(system_prompt, user_prompt, append_instruction=None, temperature=0.7):
            return responses.pop(0)

        monkeypatch.setattr(devils_advocate, "_call_devils_advocate", fake_call)
        state = _make_state()
        result = await devils_advocate.devils_advocate_node(state)
    finally:
        logger.remove(handler_id)

    out = result["agent_outputs"][0]
    assert out["retry_attempted"] is True
    assert out["forbidden_check_passed"] is False
    joined = " ".join(captured)
    assert "devils_advocate_retry_still_forbidden" in joined
