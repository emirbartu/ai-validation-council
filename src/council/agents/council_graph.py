from __future__ import annotations

import asyncio
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from council.agents.devils_advocate import devils_advocate_node
from council.agents.market_analyst import market_analyst_node
from council.agents.state import CouncilState
from council.debate.confidence import compute_confidence_from_state
from council.debate.divergence import detect_divergence
from council.debate.report import format_report
from council.logging_config import logger

MAX_ROUNDS = 2

PROFILE_ROUNDS = {
    "early_idea": 3,
    "pre_launch": 2,
    "pivot": 3,
    "full": 2,
}


def _compute_agreement_ratio(
    agent_outputs: list[dict[str, Any]], divergence_points: list[dict[str, Any]]
) -> float:
    if not divergence_points:
        return 0.0
    resolved = 0
    for div in divergence_points:
        pos_a = div.get("position_a", {}).get("claim", "")
        pos_b = div.get("position_b", {}).get("claim", "")
        agreement_markers = ["agree", "concur", "same conclusion", "both note", "similar finding"]
        if any(m in pos_a.lower() + pos_b.lower() for m in agreement_markers):
            resolved += 1
    return resolved / len(divergence_points)


def _build_counterfactual_context(agent_outputs: list[dict[str, Any]]) -> str:
    lines = ["=== COUNTERFACTUAL STRESS TEST ===", ""]
    lines.append("Your Round 1 position has been recorded. You must now construct")
    lines.append("the strongest possible argument AGAINST your own Round 1 position.")
    lines.append("This is NOT your final position — it is an adversarial stress test.")
    lines.append("")
    for output in agent_outputs:
        role = output.get("role", "unknown").replace("_", " ").title()
        content = output.get("content", "")[:1500]
        lines.append(f"--- {role}'s Round 1 Position ---")
        lines.append(content)
        lines.append("You must now argue AGAINST this position. Find every weakness.")
        lines.append("")
    return "\n".join(lines)


async def _run_agent_pair(state: CouncilState) -> dict[str, Any]:
    query = state.get("query", "")
    reddit_posts = state.get("reddit_posts", [])
    hn_stories = state.get("hn_stories", [])
    crawl_results = state.get("crawl_results", [])
    current_round = state.get("round", 0)
    prior_outputs = state.get("agent_outputs", [])
    divergence_points = state.get("divergence_points", [])

    shared: dict[str, Any] = {
        "query": query,
        "reddit_posts": reddit_posts,
        "hn_stories": hn_stories,
        "crawl_results": crawl_results,
    }

    counterfactual_triggered = state.get("counterfactual_triggered", False)

    if counterfactual_triggered and current_round == 1 and prior_outputs:
        counterfactual_context = _build_counterfactual_context(prior_outputs)
        shared["debate_context"] = counterfactual_context
    elif current_round > 0 and prior_outputs:
        debate_context = _build_debate_context(prior_outputs, divergence_points)
        shared["debate_context"] = debate_context

    try:
        markets_task = market_analyst_node(shared)
        devils_task = devils_advocate_node(shared)
        markets, devils = await asyncio.gather(markets_task, devils_task)
    except Exception as exc:
        logger.error("agent_pair_execution_failed error={}", exc)
        return {"agent_outputs": []}

    return {
        "agent_outputs": (markets.get("agent_outputs", []) + devils.get("agent_outputs", [])),
    }


async def _debate_analysis(state: CouncilState) -> dict[str, Any]:
    agent_outputs = state.get("agent_outputs", [])
    current_round = state.get("round", 0)
    logger.info("round_{}_analysis agent_count={}", current_round, len(agent_outputs))

    envelope = await detect_divergence(agent_outputs)
    divergence_status = envelope.get("status", "parsed")
    divergence_points = envelope.get("divergences", []) if divergence_status == "parsed" else []

    logger.info(
        "divergence_status status={} count={}",
        divergence_status,
        len(divergence_points),
    )

    confidence_score = compute_confidence_from_state(
        {
            "query": state.get("query", ""),
            "reddit_posts": state.get("reddit_posts", []),
            "hn_stories": state.get("hn_stories", []),
            "divergence_points": divergence_points,
            "divergence_status": divergence_status,
            "chunk_count": state.get("chunk_count", 0),
            "round": current_round,
            "agent_outputs": agent_outputs,
        },
    )

    agreement_ratio = _compute_agreement_ratio(agent_outputs, divergence_points)
    counterfactual_triggered = state.get("counterfactual_triggered", False)

    if current_round == 0 and agreement_ratio > 0.70 and not counterfactual_triggered:
        logger.warning(
            "counterfactual_triggered agreement_ratio={:.1%}",
            agreement_ratio,
        )
        counterfactual_triggered = True

    new_round = current_round + 1
    logger.info(
        "round_{}_complete divergence_count={} confidence={} next_round={}",
        current_round,
        len(divergence_points),
        confidence_score,
        new_round,
    )

    report = await format_report(
        query=state.get("query", ""),
        agent_outputs=agent_outputs,
        divergence_points=divergence_points,
        confidence_score=confidence_score,
    )

    report_dict = report.model_dump()
    report_dict["counterfactual_triggered"] = counterfactual_triggered
    report_dict["divergence_status"] = divergence_status

    return {
        "divergence_points": divergence_points,
        "divergence_status": divergence_status,
        "confidence_score": confidence_score,
        "round": new_round,
        "report": report_dict,
        "counterfactual_triggered": counterfactual_triggered,
    }


def _should_continue(state: CouncilState) -> Literal["run_agents", "end"]:
    profile = state.get("profile", "full")
    max_rounds = PROFILE_ROUNDS.get(profile, MAX_ROUNDS)
    if state.get("round", 0) >= max_rounds:
        return "end"
    return "run_agents"


def _build_debate_context(
    agent_outputs: list[dict[str, Any]],
    divergence_points: list[dict[str, Any]],
) -> str:
    lines = ["=== PREVIOUS ROUND DEBATE CONTEXT ===", ""]
    lines.append(
        "You are now in a debate round. The other council member has produced their analysis."
    )
    lines.append(
        "Read both your previous output and theirs. Challenge specific claims. Refine your position."
    )
    lines.append("Do NOT repeat your previous analysis — respond to what was said.")
    lines.append("")

    for output in agent_outputs:
        role = output.get("role", "unknown").replace("_", " ").title()
        content = output.get("content", "")
        lines.append(f"--- {role}'s Analysis ---")
        lines.append(content[:2500])
        lines.append("")

    if divergence_points:
        lines.append("--- IDENTIFIED DISAGREEMENTS ---")
        for div in divergence_points:
            lines.append(
                f"Topic: {div.get('topic', '')} | "
                f"Position A ({div.get('position_a', {}).get('agent', '?')}): "
                f"{div.get('position_a', {}).get('claim', '')[:200]} | "
                f"Position B ({div.get('position_b', {}).get('agent', '?')}): "
                f"{div.get('position_b', {}).get('claim', '')[:200]}"
            )
        lines.append("")

    lines.append("Respond to the disagreements above. Address the other member's claims directly.")
    lines.append("If you were wrong about something, say so. If they were wrong, explain why.")
    return "\n".join(lines)


def build_council_graph() -> StateGraph:
    builder = StateGraph(CouncilState)

    builder.add_node("run_agents", _run_agent_pair)
    builder.add_node("debate", _debate_analysis)

    builder.add_edge(START, "run_agents")
    builder.add_edge("run_agents", "debate")

    builder.add_conditional_edges(
        "debate",
        _should_continue,
        {
            "run_agents": "run_agents",
            "end": END,
        },
    )

    return builder


def compile_council_graph(checkpointer: Any = None) -> Any:
    builder = build_council_graph()
    if checkpointer:
        return builder.compile(checkpointer=checkpointer, interrupt_before=None)
    return builder.compile()
