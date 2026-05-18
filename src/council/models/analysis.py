"""Pydantic v2 models for analysis results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class AgentOutput(BaseModel):
    """Output from a single council agent."""

    model_config = ConfigDict(strict=True)

    role: Literal[
        "market_analyst",
        "devils_advocate",
        "icp_specialist",
        "competitive_intel",
    ]
    content: str
    citations: list[str]
    confidence: float


class DivergencePoint(BaseModel):
    """A point of disagreement between agents."""

    model_config = ConfigDict(strict=True)

    topic: str
    position_a: dict
    position_b: dict
    resolution_test: str


class AnalysisReport(BaseModel):
    """Final structured report from the council."""

    model_config = ConfigDict(strict=True)

    query: str
    agent_outputs: list[AgentOutput]
    divergence_points: list[DivergencePoint]
    confidence_score: float
    critical_assumptions: list[str]
    validation_experiments: list[str]
