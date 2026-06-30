"""Divergence detector for the AI Validation Council.

After all council members produce initial outputs, a separate LLM call
identifies every point where agents *disagree*. Agreement is not interesting.
Divergence is the signal.

Return value
------------
``detect_divergence`` now returns a **status envelope** so consumers can
distinguish a parse failure from "agents agreed". The envelope has shape::

    {
        "status": "parsed" | "parse_error" | "empty" | "insufficient_data",
        "divergences": [...],   # only populated when status == "parsed"
        "raw": "...",           # raw LLM output when status == "parse_error"
        "error": "...",         # error message when status == "parse_error"
    }

Status semantics
~~~~~~~~~~~~~~~~
* ``parsed``                — LLM responded and produced valid divergence list (possibly
                              empty when ``no_divergences`` is true).
* ``parse_error``           — LLM responded but JSON could not be parsed; ``raw`` and
                              ``error`` are populated. This is the critical fix:
                              previously the function silently returned ``[]``.
* ``empty``                 — LLM responded with a "no_divergences" explicit signal.
* ``insufficient_data``     — fewer than two agent outputs were supplied.
"""

from __future__ import annotations

import json
from typing import Any

from council.config import get_settings
from council.llm.client import get_llm_client
from council.logging_config import logger

DivergenceStatus = str

DivergenceEnvelope = dict[str, Any]

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


async def detect_divergence(agent_outputs: list[dict[str, Any]]) -> DivergenceEnvelope:
    """Detect divergences between agent outputs.

    Always returns an envelope with a ``status`` key. **Never** silently
    collapses a parse failure into an empty list.
    """
    if len(agent_outputs) < 2:
        logger.info(
            "divergence_detection_skipped reason=insufficient_agents count={}",
            len(agent_outputs),
        )
        return {
            "status": "insufficient_data",
            "divergences": [],
            "raw": "",
            "error": f"need >=2 agent outputs, got {len(agent_outputs)}",
        }

    outputs_text = _format_outputs(agent_outputs)

    try:
        client = get_llm_client()
        settings = get_settings()
        model = settings.divergence_model
        api_key = (
            settings.divergence_api_key.get_secret_value() if settings.divergence_api_key else None
        )
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
        return {
            "status": "parse_error",
            "divergences": [],
            "raw": outputs_text,
            "error": f"llm_error: {exc}",
        }

    return _parse_divergence_response(response)


def _format_outputs(outputs: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for output in outputs:
        role = output.get("role", "unknown")
        content = output.get("content", "")
        lines.append(f"--- {role.upper()} ---")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def _parse_divergence_response(text: str) -> DivergenceEnvelope:
    """Parse the raw LLM response into a status envelope.

    This function NEVER returns ``[]`` silently on a JSON parse error —
    a parse error surfaces as ``status="parse_error"`` with ``raw`` and
    ``error`` populated so the dashboard can render an explicit badge.
    """
    json_match = _extract_json(text)
    if not json_match:
        logger.warning(
            "divergence_parse_failed reason=no_json text_preview={}",
            text[:200],
        )
        return {
            "status": "parse_error",
            "divergences": [],
            "raw": text,
            "error": "no JSON object or array found in response",
        }

    try:
        data = json.loads(json_match)
    except json.JSONDecodeError as exc:
        logger.warning(
            "divergence_parse_failed reason=json_decode_error error={} text_preview={}",
            exc,
            text[:200],
        )
        return {
            "status": "parse_error",
            "divergences": [],
            "raw": text,
            "error": f"json_decode_error: {exc}",
        }
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning(
            "divergence_parse_failed reason=structural error={} text_preview={}",
            exc,
            text[:200],
        )
        return {
            "status": "parse_error",
            "divergences": [],
            "raw": text,
            "error": f"structural_error: {exc}",
        }

    if isinstance(data, list):
        return {
            "status": "parsed",
            "divergences": data,
            "raw": text,
            "error": "",
        }
    if isinstance(data, dict) and data.get("no_divergences"):
        note = data.get("note", "agents explicitly agreed")
        logger.info("divergence_detection_no_divergences note={}", note)
        return {
            "status": "empty",
            "divergences": [],
            "raw": text,
            "error": "",
        }

    logger.warning(
        "divergence_parse_failed reason=unexpected_shape value_type={}",
        type(data).__name__,
    )
    return {
        "status": "parse_error",
        "divergences": [],
        "raw": text,
        "error": f"unexpected JSON shape: top-level type={type(data).__name__}",
    }


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


def divergences_from_envelope(envelope: DivergenceEnvelope) -> list[dict[str, Any]]:
    """Backward-compat accessor.

    Returns the divergence list when ``status == "parsed"``, otherwise ``[]``.
    Use this when you only care about list semantics and already gate on
    ``status`` separately.
    """
    if envelope.get("status") == "parsed":
        return envelope.get("divergences", [])
    return []


def parse_envelope_only(parsed: list[dict[str, Any]] | DivergenceEnvelope) -> list[dict[str, Any]]:
    """Test/legacy helper: coerce list-or-envelope into ``[]`` or list."""
    if isinstance(parsed, list):
        return parsed
    return parsed.get("divergences", []) if isinstance(parsed, dict) else []


def parse_divergence_response_legacy(text: str) -> list[dict[str, Any]]:
    """Legacy parser preserved for the existing test suite.

    Returns ``[]`` on parse error so existing tests in
    ``tests/unit/test_divergence.py`` continue to pass. New code MUST
    use ``detect_divergence`` and check ``status``.
    """
    envelope = _parse_divergence_response(text)
    return divergences_from_envelope(envelope)
