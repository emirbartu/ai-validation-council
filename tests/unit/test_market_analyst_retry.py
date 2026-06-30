"""Test Market Analyst structural validation + retry loop (Module 5).

The agent must:
1. Validate the LLM response is structurally valid JSON
   (top-level keys: summary, claims, citations, assumptions).
2. If invalid, retry once at temperature=0.3 with a stricter prompt.
3. Log ``market_analyst_invalid_json`` and ``retry_attempt=1`` markers.
"""

from __future__ import annotations

import json

import pytest

from council.agents import market_analyst

SAMPLE_REDDIT = [
    {
        "id": "abc",
        "title": "AI in dental practice management",
        "url": "https://reddit.com/r/Dentistry/comments/abc/",
    }
]
SAMPLE_HN = [
    {
        "id": 100,
        "title": "Show HN: Open-source dental CRM",
        "url": "https://news.example.com/dental-crm",
        "by": "founder",
    }
]

VALID_JSON = json.dumps(
    {
        "summary": "TAM is $12B with 8% CAGR",
        "claims": [
            {
                "text": "TAM = $12B",
                "source": "https://reddit.com/r/Dentistry/comments/abc/",
                "tag": "cited",
            }
        ],
        "citations": ["https://reddit.com/r/Dentistry/comments/abc/"],
        "assumptions": [{"text": "Year 3 capture rate of 5%", "reasoning": "analog SaaS data"}],
    }
)

INVALID_PROSE = "I think the market is large and growing. TAM is about $5B. Source: my gut."


@pytest.fixture
def mock_chat(monkeypatch):
    """Force ``_call_market_analyst`` to return scripted responses."""

    responses = []

    async def fake_call(system_prompt, user_prompt, temperature=0.7):
        if responses:
            return responses.pop(0)
        return ""

    monkeypatch.setattr(market_analyst, "_call_market_analyst", fake_call)
    return responses


@pytest.fixture
def base_state():
    return {
        "query": "dental practice management software",
        "reddit_posts": SAMPLE_REDDIT,
        "hn_stories": SAMPLE_HN,
        "round": 0,
    }


class TestStructuralValidation:
    def test_valid_json_passes(self):
        assert market_analyst._is_structurally_valid_json(VALID_JSON) is True

    def test_prose_only_fails(self):
        assert market_analyst._is_structurally_valid_json(INVALID_PROSE) is False

    def test_partial_keys_fail(self):
        partial = json.dumps({"summary": "x", "claims": []})
        assert market_analyst._is_structurally_valid_json(partial) is False

    def test_empty_fails(self):
        assert market_analyst._is_structurally_valid_json("") is False

    def test_extra_keys_allowed(self):
        enriched = json.dumps(
            {
                "summary": "x",
                "claims": [],
                "citations": [],
                "assumptions": [],
                "extra": "ignored",
            }
        )
        assert market_analyst._is_structurally_valid_json(enriched) is True


class TestRetryLoop:
    @pytest.mark.asyncio
    async def test_unparseable_response_triggers_retry(self, base_state, mock_chat):
        """First call returns prose; retry returns valid JSON."""
        mock_chat.extend([INVALID_PROSE, VALID_JSON])
        result = await market_analyst.market_analyst_node(base_state)
        assert len(result["agent_outputs"]) == 1
        out = result["agent_outputs"][0]
        assert out["retry_attempted"] is True
        assert json.loads(out["content"])["summary"]

    @pytest.mark.asyncio
    async def test_valid_first_attempt_does_not_retry(self, base_state, mock_chat):
        mock_chat.append(VALID_JSON)
        result = await market_analyst.market_analyst_node(base_state)
        out = result["agent_outputs"][0]
        assert out["retry_attempted"] is False
        assert json.loads(out["content"])["summary"] == "TAM is $12B with 8% CAGR"

    @pytest.mark.asyncio
    async def test_retry_failure_falls_back_to_first_attempt(self, base_state, mock_chat):
        """If retry also fails, return first attempt — but flag retry_attempted."""
        mock_chat.extend([INVALID_PROSE, INVALID_PROSE])
        result = await market_analyst.market_analyst_node(base_state)
        out = result["agent_outputs"][0]
        assert out["retry_attempted"] is True
        assert out["content"] == INVALID_PROSE

    @pytest.mark.asyncio
    async def test_retry_called_with_temperature_three(self, base_state, monkeypatch):
        """Confirm retry uses temperature=0.3 (Module 5 spec)."""
        temps_seen: list[float] = []

        async def fake_call(system_prompt, user_prompt, temperature=0.7):
            temps_seen.append(temperature)
            if len(temps_seen) == 1:
                return INVALID_PROSE
            return VALID_JSON

        monkeypatch.setattr(market_analyst, "_call_market_analyst", fake_call)
        await market_analyst.market_analyst_node(base_state)
        assert temps_seen[0] == 0.7
        assert temps_seen[1] == 0.3

    @pytest.mark.asyncio
    async def test_invalid_json_log_contains_retry_marker(self, base_state, mock_chat):
        import json

        from council.logging_config import logger

        captured: list[str] = []

        def sink(message: str) -> None:
            record = json.loads(message)
            captured.append(record["record"]["message"])

        handler_id = logger.add(sink, level="WARNING", serialize=True)
        try:
            mock_chat.extend([INVALID_PROSE, VALID_JSON])
            await market_analyst.market_analyst_node(base_state)
        finally:
            logger.remove(handler_id)
        joined = " ".join(captured)
        assert "market_analyst_invalid_json" in joined
        assert "retry_attempt=1" in joined


class TestCitationVerificationRunsAfterRetry:
    @pytest.mark.asyncio
    async def test_citation_checks_populated(self, base_state, mock_chat):
        valid_with_real_url = json.dumps(
            {
                "summary": "x",
                "claims": [
                    {
                        "text": "y",
                        "source": "https://reddit.com/r/Dentistry/comments/abc/",
                        "tag": "cited",
                    }
                ],
                "citations": ["https://reddit.com/r/Dentistry/comments/abc/"],
                "assumptions": [],
            }
        )
        mock_chat.append(valid_with_real_url)
        result = await market_analyst.market_analyst_node(base_state)
        out = result["agent_outputs"][0]
        assert "citation_checks" in out
        assert out["citation_checks"][0]["verified"] is True
        assert out["citations"] == ["https://reddit.com/r/Dentistry/comments/abc/"]
