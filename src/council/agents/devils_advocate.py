"""Devil's Advocate agent node for the AI Validation Council.

This is the most critical agent in the council. It enforces the anti-sycophancy
system by rejecting encouraging or optimistic language and demanding structural,
data-backed failure analysis.
"""

from __future__ import annotations

import re
from typing import Any

from council.agents.prompts import build_system_prompt, load_skill_file
from council.config import LLMRole, resolve_llm_config
from council.debate.citation_verification import verify_citations
from council.llm.client import get_llm_client
from council.logging_config import logger

_MAX_RETRIES = 1

_WORD_LIMITS = {0: 400, 1: 300, 2: 150}


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


_URL_RE = re.compile(r"https?://[^\s\)\]\>\"]+", re.IGNORECASE)

_KILL_SHOT_RE = re.compile(
    r"(?:^|\n)\s*(?:#+\s*)?Kill\s+Shot\s+(\d+)[:\.\s\-]+([^\n]+)",
    re.IGNORECASE,
)
_KILL_SHOT_SECTION_RE = re.compile(
    r"Kill\s+Shot\s+\d+[:\.\s\-]+(.+?)(?=\n\s*(?:Kill\s+Shot\s+\d+|The\s+Fatal|Named\s+Competitor|Data\s+Limitation|$))",
    re.IGNORECASE | re.DOTALL,
)

_VERDICT_RE = re.compile(
    r"^(?:###?\s*)?(?:One-Sentence\s+)?Verdict[:\.]?\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

_FORBIDDEN_EXACT = [
    "However, there are also opportunities...",
    "With the right team, this could work",
    "This is a promising concept",
    "There is potential if...",
    "The idea has merit",
    "While challenges exist...",
    "but if you can overcome these challenges...",
    "this analysis is meant to stress-test, not discourage",
    "ultimately, the market will decide",
]

_ENCOURAGEMENT_ENDINGS = [
    "great potential",
    "bright future",
    "could succeed",
    "will succeed",
    "promising future",
    "strong potential",
    "good potential",
    "high potential",
    "worth pursuing",
    "worth considering",
    "may succeed",
    "might succeed",
    "has potential",
]

_POSITIVE_SENTIMENT_WORDS = [
    "opportunity",
    "opportunities",
    "potential",
    "promising",
    "merit",
    "could work",
    "might work",
    "worth exploring",
    "worth investigating",
    "exciting",
    "optimistic",
    "hopeful",
]


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


def check_forbidden_phrases(text: str) -> tuple[bool, list[str]]:
    """Check *text* against all forbidden phrase patterns.

    Returns
    -------
    (has_forbidden, detected_phrases)
        ``has_forbidden`` is ``True`` if any forbidden content was found.
        ``detected_phrases`` is the ordered list of unique matches.
    """
    detected: list[str] = []
    text_lower = text.lower()

    for phrase in _FORBIDDEN_EXACT:
        if phrase.lower() in text_lower:
            detected.append(phrase)

    if "with the right" in text_lower:
        match = re.search(r"with the right[^.\n]{0,80}", text_lower)
        context = match.group(0) if match else "with the right..."
        detected.append(context)

    sentences = re.split(r"[.!?\n]+", text)
    for sentence in sentences:
        stripped = sentence.strip().lower().rstrip(".!?:;,")
        for ending in _ENCOURAGEMENT_ENDINGS:
            if stripped.endswith(ending.lower()):
                detected.append(f"Encouraging ending: '{sentence.strip()}'")
                break

    however_clauses = re.findall(
        r"However,\s*([^\.\n]{0,200})",
        text,
        re.IGNORECASE,
    )
    for clause in however_clauses:
        clause_lower = clause.lower()
        for word in _POSITIVE_SENTIMENT_WORDS:
            if word.lower() in clause_lower:
                detected.append(
                    f"However + positive sentiment: 'However, {clause.strip()}'",
                )
                break

    unique_detected: list[str] = []
    seen: set[str] = set()
    for d in detected:
        key = d.lower()
        if key not in seen:
            seen.add(key)
            unique_detected.append(d)

    return (bool(unique_detected), unique_detected)


def extract_kill_shots(text: str) -> list[dict[str, str]]:
    sections = list(_KILL_SHOT_SECTION_RE.finditer(text))

    if not sections:
        titles = list(_KILL_SHOT_RE.finditer(text))
        return [{"number": m.group(1), "title": m.group(2).strip(), "details": ""} for m in titles]

    kill_shots: list[dict[str, str]] = []
    for i, m in enumerate(sections):
        details = m.group(1).strip()[:1500]
        title_match = _KILL_SHOT_RE.search(m.group(0))
        number = title_match.group(1) if title_match else str(i + 1)
        title = title_match.group(2).strip() if title_match else details[:100]
        kill_shots.append({"number": number, "title": title, "details": details})

    return kill_shots


def extract_verdict(text: str) -> str:
    """Extract the one-sentence verdict from the response.

    Looks for an explicit ``Verdict:`` label; if missing, returns the first
    non-empty line.
    """
    match = _VERDICT_RE.search(text)
    if match:
        return match.group(1).strip()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


async def _call_devils_advocate(
    system_prompt: str,
    user_prompt: str,
    append_instruction: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Call the Devil's Advocate LLM with optional appended instruction.

    Module 5: retried calls (e.g. after sycophancy detection) drop to
    ``temperature=0.3`` for more deterministic, harsher output.
    """
    full_system = system_prompt
    if append_instruction:
        full_system = f"{system_prompt}\n\n{append_instruction}"

    client = get_llm_client()
    resolved = resolve_llm_config(LLMRole.DEVILS_ADVOCATE)
    return await client.achat(
        model_key=resolved.model,
        system_prompt=full_system,
        user_prompt=user_prompt,
        temperature=temperature,
        api_key_override=resolved.api_key,
        base_url_override=resolved.base_url,
    )


async def devils_advocate_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: run the Devil's Advocate agent.

    Expects *state* to contain at minimum:
    - ``query`` (str): the user's validation query.
    - ``reddit_posts`` (list): collected Reddit posts.
    - ``hn_stories`` (list): collected Hacker News stories.

    Returns a dict with an ``agent_outputs`` list containing the structured
    Devil's Advocate output.
    """
    query = state.get("query", "")
    reddit_posts = state.get("reddit_posts", [])
    hn_stories = state.get("hn_stories", [])

    skills = load_skill_file("devils_advocate")
    if not skills:
        logger.warning("devils_advocate_missing_skills")

    context_data: dict[str, Any] = {
        "reddit_posts": reddit_posts,
        "hn_stories": hn_stories,
    }

    system_prompt = build_system_prompt("devils_advocate", query, context_data)
    user_prompt = (
        "Find the structural failure modes for the query above. "
        "Follow the structured format defined in your SKILLS file. "
        "Be harsh, specific, and data-backed."
    )

    debate_context = state.get("debate_context", "")
    if debate_context:
        system_prompt = f"{system_prompt}\n\n{debate_context}"
        user_prompt = (
            "This is a debate round. The market analyst has made claims about the opportunity. "
            "Challenge their specific numbers and assumptions. Name what they got wrong. "
            "Your kill shots should now ALSO address their specific claims."
        )

    round_num = state.get("round", 0)
    word_limit_note = (
        f"\n\n[SYSTEM] Your response must not exceed {_WORD_LIMITS.get(round_num, 400)} words. "
        "Prioritize precision over comprehensiveness."
    )
    system_prompt = system_prompt + word_limit_note

    try:
        response_text = await _call_devils_advocate(system_prompt, user_prompt)
    except Exception as exc:
        logger.error("devils_advocate_llm_error error={} trace_id={}", exc, "")
        return {"agent_outputs": []}

    if not response_text:
        logger.warning("devils_advocate_empty_response")
        return {"agent_outputs": []}

    forbidden_check_passed = True
    retry_attempted = False

    has_forbidden, detected = check_forbidden_phrases(response_text)
    if has_forbidden:
        forbidden_check_passed = False
        retry_attempted = True
        logger.warning(
            "devils_advocate_sycophancy_detected phrases={}",
            detected,
        )
        logger.warning(
            "devils_advocate_retry_attempt=1 reason=sycophancy phrases={}",
            detected,
        )

        retry_instruction = (
            "YOUR PREVIOUS RESPONSE WAS REJECTED because it contained forbidden phrases. "
            f"Your role is to find failure modes, not to be encouraging. "
            f"Rewrite without any of these: {', '.join(detected)}. "
            "Be harsher. Find more structural reasons for failure. "
            "Do not soften language even in concluding sentences."
        )

        try:
            response_text = await _call_devils_advocate(
                system_prompt,
                user_prompt,
                retry_instruction,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error(
                "devils_advocate_retry_llm_error error={} trace_id={}",
                exc,
                "",
            )

        if response_text:
            has_forbidden_after_retry, detected_after_retry = check_forbidden_phrases(response_text)
            if not has_forbidden_after_retry:
                forbidden_check_passed = True
            else:
                logger.warning(
                    "devils_advocate_retry_still_forbidden phrases={}",
                    detected_after_retry,
                )

    response_text = _enforce_word_limit(response_text, round_num, "devils_advocate")

    _extract_citations(response_text)
    kill_shots = extract_kill_shots(response_text)
    verdict = extract_verdict(response_text)

    if len(kill_shots) < 3:
        logger.warning(
            "devils_advocate_insufficient_kill_shots count={} expected=3",
            len(kill_shots),
        )

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
                "role": "devils_advocate",
                "content": response_text,
                "kill_shots": kill_shots,
                "verdict": verdict,
                "forbidden_check_passed": forbidden_check_passed,
                "retry_attempted": retry_attempted,
                "citations": verified_citations,
                "citation_checks": citation_checks,
                "confidence": 0.0,
            },
        ],
    }
