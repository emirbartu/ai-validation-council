"""Market Analyst agent node for the AI Validation Council."""

from __future__ import annotations

import re
from typing import Any

from council.agents.prompts import build_system_prompt, load_skill_file
from council.config import get_settings
from council.llm.client import get_llm_client
from council.logging_config import get_trace_id, logger

_URL_RE = re.compile(r"https?://[^\s\)\]\>\"]+", re.IGNORECASE)

_WORD_LIMITS = {0: 400, 1: 300, 2: 150}


def _enforce_word_limit(text: str, round_num: int, agent_name: str) -> str:
    limit = _WORD_LIMITS.get(round_num, 400)
    words = text.split()
    if len(words) > limit:
        logger.warning(
            "word_limit_exceeded agent={} round={} words={} limit={}",
            agent_name, round_num, len(words), limit,
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


async def market_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: run the Market Analyst agent.

    Expects *state* to contain at minimum:
    - ``query`` (str): the user's validation query.
    - ``reddit_posts`` (list): collected Reddit posts.
    - ``hn_stories`` (list): collected Hacker News stories.

    Returns a dict with an ``agent_outputs`` list.
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

    try:
        client = get_llm_client()
        settings = get_settings()
        model = settings.market_analyst_model
        api_key = settings.market_analyst_api_key.get_secret_value() if settings.market_analyst_api_key else None
        base_url = settings.market_analyst_base_url

        if not base_url:
            base_url = ""

        response_text = await client.achat(
            model_key=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            api_key_override=api_key if api_key else None,
            base_url_override=base_url,
        )
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
    citations = _extract_citations(response_text)

    return {
        "agent_outputs": [
            {
                "role": "market_analyst",
                "content": response_text,
                "citations": citations,
                "confidence": 0.0,
            },
        ],
    }
