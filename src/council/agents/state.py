"""LangGraph state definition for the AI Validation Council.

Uses TypedDict with ``Annotated[...]`` reducers so parallel agent nodes
can safely write to the same state keys.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class CouncilState(TypedDict):
    query: str
    reddit_posts: list[dict[str, Any]]
    hn_stories: list[dict[str, Any]]
    crawl_results: list[dict[str, Any]]
    enabled_sources: list[str]
    agent_outputs: Annotated[list[dict[str, Any]], operator.add]
    divergence_points: list[dict[str, Any]]
    divergence_status: str | None
    confidence_score: float
    round: int
    error: str | None
    chunk_count: int
    report: dict[str, Any] | None
    counterfactual_triggered: bool
    profile: str
