"""Confidence score calculation per the master plan formula.

Score decreases with more disagreement — this is intentional.
More divergence = more uncertainty = lower score = more research needed.
"""

from __future__ import annotations

import math
from typing import Any

from council.config import get_settings
from council.logging_config import logger

# Module-level cache for convergence tracking across debate rounds.
_prev_divergence_by_query: dict[str, int] = {}


def sigmoid_penalty(divergence_count: int, steepness: float = 1.5, midpoint: float = 3.0) -> float:
    """Non-linear divergence penalty using sigmoid.
    1-2 divergences = mild penalty, 3-4 = steep, 5+ = saturating."""
    return 25.0 / (1.0 + math.exp(-steepness * (divergence_count - midpoint)))


def debate_depth_factor(rounds: int, convergence_rate: float) -> float:
    """Bonus/penalty for multi-round debate. Convergence = agents narrowing disagreements."""
    if rounds <= 1:
        return 0.0
    # Convergence rate: 0 = total disagreement grew, 1 = fully resolved
    return 10.0 * (2.0 * convergence_rate - 1.0) * math.log(rounds + 1) / math.log(3)


def data_quality_factor(citations_count: int) -> float:
    """Reward analyses with more citations (0-10 scale)."""
    return min(10.0, citations_count * 1.5)


def calculate_confidence_score_v2(
    data_volume: int,
    divergence_count: int = 0,
    source_diversity: int = 1,
    recency_score: float = 0.5,
    rounds: int = 1,
    convergence_rate: float = 0.0,
    citations_count: int = 0,
    enabled_sources: int = 2,
) -> float:
    # 1. Volume (0-30): sigmoid saturation
    volume = 30.0 / (1.0 + math.exp(-0.03 * (data_volume - 40)))

    # 2. Diversity (0-20): ratio of populated sources to enabled
    diversity_ratio = min(source_diversity, enabled_sources) / max(enabled_sources, 1)
    diversity = 20.0 * diversity_ratio

    # 3. Recency (0-20): unchanged from v1
    recency = recency_score * 20.0

    # 4. Non-linear divergence penalty
    penalty = sigmoid_penalty(divergence_count)

    # 5. Debate depth bonus
    depth = debate_depth_factor(rounds, convergence_rate)

    # 6. Data quality
    quality = data_quality_factor(citations_count)

    raw = volume + diversity + recency - penalty + depth + quality
    return max(0.0, min(100.0, round(raw, 1)))


def calculate_confidence_score(
    data_volume: int,
    divergence_count: int = 0,
    source_diversity: int = 1,
    recency_score: float = 0.5,
) -> float:
    """Backward-compatible v1 confidence score."""
    base = min(data_volume / 200, 1.0) * 40
    diversity = (source_diversity / 5) * 20
    recency = recency_score * 20
    divergence_penalty = divergence_count * 5

    raw = base + diversity + recency - divergence_penalty
    score = max(0.0, min(100.0, raw))
    return round(score, 1)


def compute_confidence_from_state(state: dict[str, Any]) -> float:
    data_volume = (
        len(state.get("reddit_posts", []))
        + len(state.get("hn_stories", []))
        + len(state.get("crawl_results", []))
    )
    chunk_count = state.get("chunk_count", 0)
    if chunk_count > 0:
        data_volume = chunk_count
    divergence_count = len(state.get("divergence_points", []))
    source_diversity = _count_sources(state)
    recency_score = _compute_recency(
        state.get("reddit_posts", []),
        state.get("hn_stories", []),
    )

    # Determine how many sources are configured in settings
    settings = get_settings()
    enabled_sources = 1  # HN is always enabled
    if settings.serper_api_key:
        enabled_sources += 1

    rounds = state.get("round", 0)

    # Compute convergence rate by comparing with previous round's divergence
    query = state.get("query", "")
    if rounds > 1 and query in _prev_divergence_by_query:
        prev_divergence = _prev_divergence_by_query[query]
        if prev_divergence > 0:
            convergence_rate = 1.0 - (divergence_count / prev_divergence)
        else:
            convergence_rate = 0.0 if divergence_count == 0 else -1.0
    else:
        convergence_rate = 0.0

    # Cache current divergence for next round
    _prev_divergence_by_query[query] = divergence_count

    # Count citations across all agent outputs
    agent_outputs = state.get("agent_outputs", [])
    citations_count = sum(len(o.get("citations", [])) for o in agent_outputs)

    score = calculate_confidence_score_v2(
        data_volume=data_volume,
        divergence_count=divergence_count,
        source_diversity=source_diversity,
        recency_score=recency_score,
        rounds=rounds,
        convergence_rate=convergence_rate,
        citations_count=citations_count,
        enabled_sources=enabled_sources,
    )

    logger.info(
        "confidence_score computed score={} data_volume={} chunks={} divergence_count={} "
        "source_diversity={} recency={} convergence_rate={} citations_count={}",
        score,
        len(state.get("reddit_posts", []))
        + len(state.get("hn_stories", []))
        + len(state.get("crawl_results", [])),
        chunk_count,
        divergence_count,
        source_diversity,
        recency_score,
        convergence_rate,
        citations_count,
    )

    return score


def _count_sources(state: dict[str, Any]) -> int:
    count = 0
    if state.get("reddit_posts"):
        count += 1
    if state.get("hn_stories"):
        count += 1
    if state.get("crawl_results"):
        count += 1
    return min(count, 5)


def _compute_recency(
    reddit_posts: list[dict[str, Any]],
    hn_stories: list[dict[str, Any]],
) -> float:
    import time as _time

    now = _time.time()
    timestamps: list[float] = []
    for p in reddit_posts:
        ts = p.get("created_utc", 0) if isinstance(p, dict) else getattr(p, "created_utc", 0)
        if ts and ts > 0:
            timestamps.append(ts)
    for s in hn_stories:
        ts = s.get("time", 0) if isinstance(s, dict) else getattr(s, "time", 0)
        if ts and ts > 0:
            timestamps.append(ts)
    if not timestamps:
        return 0.5
    avg_age = now - (sum(timestamps) / len(timestamps))
    if avg_age < 86400:
        return 1.0
    if avg_age < 604800:
        return 0.8
    if avg_age < 2592000:
        return 0.6
    if avg_age < 7776000:
        return 0.4
    return 0.2


def interpret_score(score: float) -> str:
    if score >= 80:
        return "High confidence — strong data, minimal disagreement"
    if score >= 60:
        return "Moderate confidence — reasonable data, some divergent views"
    if score >= 40:
        return "Low confidence — limited data or significant disagreement"
    if score >= 20:
        return "Very low confidence — insufficient data or major disagreements"
    return "Unreliable — critical data or consensus gaps. More research required."
