"""Divergence detector for the AI Validation Council.

After all council members produce initial outputs, a separate LLM call
identifies every point where agents *disagree*. Agreement is not interesting.
Divergence is the signal.
"""

from __future__ import annotations

import json
from typing import Any

from council.config import get_settings
from council.llm.client import get_llm_client
from council.logging_config import logger

_DIVERGENCE_SYSTEM_PROMPT = """You are analyzing outputs from market analysts who reviewed the same startup idea. Your ONLY job is to find where they DISAGREE.

Do not summarize where they agree. Agreement is not interesting.
Find every point of contradiction. For each divergence:
1. Topic heading
2. Position A: [who] says [what]
3. Position B: [who] says [what]
4. What specific data or test would resolve this disagreement?

If there are no real divergences, say so explicitly. This means the council has failed to think independently.

Return a JSON array of divergence objects:
[
  {
    "topic": "string",
    "position_a": {"agent": "string", "claim": "string"},
    "position_b": {"agent": "string", "claim": "string"},
    "resolution_test": "string"
  }
]

If no divergences found, return: {"no_divergences": true, "note": "string"}
"""


async def detect_divergence(agent_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(agent_outputs) < 2:
        logger.info("divergence_detection_skipped reason=insufficient_agents count={}", len(agent_outputs))
        return []

    outputs_text = _format_outputs(agent_outputs)

    try:
        client = get_llm_client()
        settings = get_settings()
        model = settings.divergence_model
        api_key = settings.divergence_api_key.get_secret_value() if settings.divergence_api_key else None
        base_url = settings.divergence_base_url

        if not base_url:
            base_url = ""

        response = await client.achat(
            model_key=model,
            system_prompt=_DIVERGENCE_SYSTEM_PROMPT,
            user_prompt=outputs_text,
            temperature=0.3,
            api_key_override=api_key if api_key else None,
            base_url_override=base_url,
        )
    except Exception as exc:
        logger.error("divergence_llm_error error={}", exc)
        return []

    divergences = _parse_divergence_response(response)
    return divergences


def _format_outputs(outputs: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for output in outputs:
        role = output.get("role", "unknown")
        content = output.get("content", "")
        lines.append(f"--- {role.upper()} ---")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def _parse_divergence_response(text: str) -> list[dict[str, Any]]:
    try:
        json_match = _extract_json(text)
        if json_match:
            data = json.loads(json_match)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and data.get("no_divergences"):
                logger.info("divergence_detection_no_divergences note={}", data.get("note"))
                return []
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("divergence_parse_failed error={} text_preview={}", exc, text[:200])

    return []


def _extract_json(text: str) -> str | None:
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return None
