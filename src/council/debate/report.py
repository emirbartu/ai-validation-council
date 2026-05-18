"""LLM-based report formatter that extracts structured data from council outputs."""

from __future__ import annotations

import json
from typing import Any

from council.config import get_settings
from council.debate.confidence import interpret_score
from council.llm.client import get_llm_client
from council.logging_config import logger
from council.models.report import (
    AnalysisReport,
    CouncilAddendum,
    CriticalAssumption,
    DebateSummary,
    DivergenceItem,
    RiskItem,
    SWOTAnalysis,
    ValidationExperiment,
)

_EXTRACTION_PROMPT = """You are a structured data extraction engine.
Given council agent outputs analyzing a startup idea, extract ALL fields below.

Respond ONLY with valid JSON. No markdown, no explanations.

Agent outputs:
{agent_outputs}

Return this exact JSON structure:
{{
  "risks": [...],
  "critical_assumptions": [...],
  "validation_experiments": [...],
  "debate_summary": {{
    "what_agents_agreed_on": ["one-sentence consensus point", ...],
    "what_would_strengthen_the_idea": ["specific actionable improvement", ...],
    "key_disadvantages": ["structural weakness all agents flagged", ...]
  }},
  "swot": {{
    "strengths": ["data-backed internal strength", ...],
    "weaknesses": ["internal limitation of the idea", ...],
    "opportunities": ["external condition with data reference", ...],
    "threats": ["external force — most dangerous first", ...]
  }},
  "addendum": null
}}

STRICT RULES:
- Each SWOT item: one sentence, specific, data-referenced. "Large market" is invalid.
- SWOT: 2-5 items per quadrant. Rank threats by immediacy × severity (most dangerous first).
- debate_summary.key_disadvantages: structural weaknesses ALL agents flagged (not from one agent).
- If a category has no valid items, return an empty array/list.
- addendum: ALWAYS set to null. The addendum is handled by a separate process.
"""


async def _extract_structured_data(agent_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    client = get_llm_client()
    settings = get_settings()
    model = settings.report_model
    api_key = settings.report_api_key.get_secret_value() if settings.report_api_key else None
    base_url = settings.report_base_url

    if not base_url and settings.report_provider:
        base_url = settings.report_base_url

    if not base_url:
        base_url = ""

    try:
        prompt = _EXTRACTION_PROMPT.format(agent_outputs=json.dumps(agent_outputs, indent=2))
        response = await client.achat(
            model_key=model,
            system_prompt="You extract structured data from unstructured text. Output valid JSON only.",
            user_prompt=prompt,
            temperature=0.1,
            api_key_override=api_key if api_key else None,
            base_url_override=base_url,
        )
        content = response.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        return json.loads(content)
    except Exception as exc:
        logger.warning("report_extraction_failed error={}", str(exc)[:200])
        return {"risks": [], "critical_assumptions": [], "validation_experiments": [],
                "debate_summary": {}, "swot": {}, "addendum": None}


def _map_divergence_points(
    divergence_points: list[dict[str, Any]],
) -> list[DivergenceItem]:
    items: list[DivergenceItem] = []
    for div in divergence_points:
        pos_a = div.get("position_a", {})
        pos_b = div.get("position_b", {})
        if isinstance(pos_a, dict):
            pos_a_str = f"{pos_a.get('agent', 'Agent A')}: {pos_a.get('claim', '')}"
        else:
            pos_a_str = str(pos_a)
        if isinstance(pos_b, dict):
            pos_b_str = f"{pos_b.get('agent', 'Agent B')}: {pos_b.get('claim', '')}"
        else:
            pos_b_str = str(pos_b)
        items.append(
            DivergenceItem(
                topic=div.get("topic", ""),
                position_a=pos_a_str,
                position_b=pos_b_str,
                resolution_test=div.get("resolution_test", ""),
            )
        )
    return items


async def format_report(
    query: str,
    agent_outputs: list[dict[str, Any]],
    divergence_points: list[dict[str, Any]],
    confidence_score: float,
) -> AnalysisReport:
    """Format council outputs into a structured AnalysisReport.

    Uses LLM-based extraction to pull risks, assumptions, and experiments
    from unstructured agent text, with graceful fallback to empty lists.
    """
    structured = await _extract_structured_data(agent_outputs)

    risks: list[RiskItem] = []
    for r in structured.get("risks", []):
        try:
            risks.append(
                RiskItem(
                    name=r.get("name", ""),
                    severity=r.get("severity", 5),
                    probability=r.get("probability", 5),
                    reversibility=r.get("reversibility", 5),
                    description=r.get("description", ""),
                )
            )
        except Exception as exc:
            logger.warning("risk_parsing_failed error={}", str(exc)[:200])

    assumptions: list[CriticalAssumption] = []
    for a in structured.get("critical_assumptions", []):
        try:
            assumptions.append(
                CriticalAssumption(
                    assumption=a.get("assumption", ""),
                    why_critical=a.get("why_critical", ""),
                    evidence_strength=a.get("evidence_strength", "weak"),
                    evidence_summary=a.get("evidence_summary", ""),
                )
            )
        except Exception as exc:
            logger.warning("assumption_parsing_failed error={}", str(exc)[:200])

    experiments: list[ValidationExperiment] = []
    for e in structured.get("validation_experiments", []):
        try:
            experiments.append(
                ValidationExperiment(
                    name=e.get("name", ""),
                    cost_estimate=e.get("cost_estimate", ""),
                    time_required=e.get("time_required", ""),
                    success_criteria=e.get("success_criteria", ""),
                    what_it_tests=e.get("what_it_tests", ""),
                )
            )
        except Exception as exc:
            logger.warning("experiment_parsing_failed error={}", str(exc)[:200])

    # Parse debate summary
    ds_data = structured.get("debate_summary", {})
    debate_summary = DebateSummary(
        what_agents_agreed_on=ds_data.get("what_agents_agreed_on", []),
        what_would_strengthen_the_idea=ds_data.get("what_would_strengthen_the_idea", []),
        key_disadvantages=ds_data.get("key_disadvantages", []),
    )

    # Parse SWOT
    swot_data = structured.get("swot", {})
    swot = SWOTAnalysis(
        strengths=swot_data.get("strengths", []),
        weaknesses=swot_data.get("weaknesses", []),
        opportunities=swot_data.get("opportunities", []),
        threats=swot_data.get("threats", []),
    )

    # Parse addendum — strict: only populate if LLM explicitly returned it AND it's not null
    addendum: CouncilAddendum | None = None
    ad_data = structured.get("addendum")
    if ad_data and isinstance(ad_data, dict) and ad_data.get("topic"):
        try:
            addendum = CouncilAddendum(
                topic=ad_data.get("topic", ""),
                insight=ad_data.get("insight", ""),
                raised_by=ad_data.get("raised_by", ""),
            )
        except Exception as exc:
            logger.warning("addendum_parsing_failed error={}", str(exc)[:200])
    # Validate addendum is not redundant with other fields (addendum check)
    if addendum is not None:
        all_text = (
            " ".join(debate_summary.what_agents_agreed_on)
            + " ".join(debate_summary.what_would_strengthen_the_idea)
            + " ".join(debate_summary.key_disadvantages)
            + " ".join(swot.strengths)
            + " ".join(swot.weaknesses)
            + " ".join(swot.opportunities)
            + " ".join(swot.threats)
            + " ".join(r.name + r.description for r in risks)
            + " ".join(a.assumption for a in assumptions)
            + " ".join(e.name for e in experiments)
        )
        if addendum.insight.lower() in all_text.lower():
            logger.info("addendum_discarded reason=redundant")
            addendum = None

    return AnalysisReport(
        query=query,
        divergence_report=_map_divergence_points(divergence_points),
        risk_ranking=risks,
        critical_assumptions=assumptions,
        validation_experiments=experiments,
        confidence_score=confidence_score,
        confidence_interpretation=interpret_score(confidence_score),
        agent_outputs=agent_outputs,
        debate_summary=debate_summary,
        swot=swot,
        addendum=addendum,
    )
