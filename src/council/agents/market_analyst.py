"""Market Analyst agent node for the AI Validation Council."""

from __future__ import annotations

import json
import re
from typing import Any

from council.agents.prompts import build_system_prompt, load_skill_file
from council.config import LLMRole, resolve_llm_config
from council.debate.citation_verification import verify_citations
from council.llm.client import get_llm_client
from council.logging_config import get_trace_id, logger

_URL_RE = re.compile(r"https?://[^\s\)\]\>\"]+", re.IGNORECASE)

_WORD_LIMITS = {0: 400, 1: 300, 2: 150}

_MAX_RETRIES = 1

_STRICT_RETRY_INSTRUCTION = (
    "Your previous response was structurally invalid. You MUST now respond with "
    "valid JSON containing EXACTLY these top-level keys: "
    '"summary", "claims", "citations", "assumptions". '
    "Every numerical claim must cite a collected source URL/title or be labelled "
    '"[ASSUMPTION]". No prose outside the JSON. No markdown fences. '
    "Respond now with the JSON object only."
)


def _enforce_word_limit(text: str, round_num: int, agent_name: str) -> str:
    limit = _WORD_LIMITS.get(round_num, 400)
    words = text.split()
    if len(words) > limit:
        logger.warning(
            "word_limit_exceeded agent={} round={} words={} limit={}",
            agent_name,
            round_num,
            len(words),
            limit,
        )
        return " ".join(words[:limit]) + "..."
    return text


def _extract_citations(text: str) -> list[str]:
    """Pull URLs and explicit source mentions out of the LLM response."""
    urls = _URL_RE.findall(text)
    source_mentions = re.findall(
        r"(?:Source|From|Via|According to)[\s:]+([^\n\.]+)",
        text,
        re.IGNORECASE,
    )
    citations = urls + [s.strip() for s in source_mentions if s.strip()]
    return list(dict.fromkeys(citations))


def _to_dict(obj: Any) -> dict[str, Any]:
    """Normalise a model instance or dict into a plain dict."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}


def _is_structurally_valid_json(text: str) -> bool:
    """Return True iff ``text`` parses as a JSON object with the required keys.

    Required keys (Module 5 spec): ``summary``, ``claims``, ``citations``, ``assumptions``.
    Plain-prose responses that happen to contain a citation are not sufficient —
    the analyst output must be machine-parseable so it can be verified.
    """
    if not text:
        return False
    json_match = _extract_json_object(text)
    if not json_match:
        return False
    try:
        data = json.loads(json_match)
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    required = {"summary", "claims", "citations", "assumptions"}
    return required.issubset(data.keys())


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


async def _call_market_analyst(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
) -> str:
    client = get_llm_client()
    resolved = resolve_llm_config(LLMRole.MARKET_ANALYST)
    return await client.achat(
        model_key=resolved.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        api_key_override=resolved.api_key,
        base_url_override=resolved.base_url,
    )


async def market_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: run the Market Analyst agent.

    Expects *state* to contain at minimum:
    - ``query`` (str): the user's validation query.
    - ``reddit_posts`` (list): collected Reddit posts.
    - ``hn_stories`` (list): collected Hacker News stories.

    Returns a dict with an ``agent_outputs`` list.

    Module 5 contract: if the LLM response fails structural JSON validation,
    retry once at temperature=0.3 with a strict prompt reminder. Logs
    ``retry_attempt=1`` in that case.
    """
    query = state.get("query", "")
    reddit_posts = [_to_dict(p) for p in state.get("reddit_posts", [])]
    hn_stories = [_to_dict(s) for s in state.get("hn_stories", [])]

    skills = load_skill_file("market_analyst")
    if not skills:
        logger.warning("market_analyst_missing_skills")

    context_data: dict[str, Any] = {
        "reddit_posts": reddit_posts,
        "hn_stories": hn_stories,
    }

    system_prompt = build_system_prompt("market_analyst", query, context_data)
    user_prompt = (
        "Analyze the market opportunity for the query above. "
        "Follow the structured format defined in your SKILLS file."
    )

    debate_context = state.get("debate_context", "")
    if debate_context:
        system_prompt = f"{system_prompt}\n\n{debate_context}"
        user_prompt = (
            "This is a debate round. Address the other council member's claims. "
            "Challenge or refine your position based on what they said."
        )

    round_num = state.get("round", 0)
    word_limit_note = (
        f"\n\n[SYSTEM] Your response must not exceed {_WORD_LIMITS.get(round_num, 400)} words. "
        "Prioritize precision over comprehensiveness."
    )
    system_prompt = system_prompt + word_limit_note

    retry_attempted = False
    try:
        response_text = await _call_market_analyst(system_prompt, user_prompt)
    except Exception as exc:
        logger.error(
            "market_analyst_llm_error error={} trace_id={}",
            exc,
            get_trace_id(),
        )
        return {"agent_outputs": []}

    if not response_text:
        logger.warning("market_analyst_empty_response")
        return {"agent_outputs": []}

    response_text = _enforce_word_limit(response_text, round_num, "market_analyst")

    if not _is_structurally_valid_json(response_text):
        logger.warning(
            "market_analyst_invalid_json retry_attempt=1 round={} preview={}",
            round_num,
            response_text[:200],
        )
        retry_attempted = True
        try:
            retry_text = await _call_market_analyst(
                system_prompt + "\n\n" + _STRICT_RETRY_INSTRUCTION,
                user_prompt,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error(
                "market_analyst_retry_llm_error error={} trace_id={}",
                exc,
                get_trace_id(),
            )
            retry_text = ""

        if retry_text and _is_structurally_valid_json(retry_text):
            response_text = retry_text

    raw_citations = _extract_citations(response_text)
    citation_checks = verify_citations(
        raw_citations,
        reddit_posts,
        hn_stories,
    )

    verified_citations = [c["value"] for c in citation_checks if c["verified"]]

    return {
        "agent_outputs": [
            {
                "role": "market_analyst",
                "content": response_text,
                "citations": verified_citations,
                "citation_checks": citation_checks,
                "confidence": 0.0,
                "retry_attempted": retry_attempted,
            },
        ],
    }
