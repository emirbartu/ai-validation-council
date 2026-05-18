"""Pydantic v2 models for structured analysis reports (Layer 5)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DivergenceItem(BaseModel):
    """A single disagreement between council agents."""

    model_config = ConfigDict(strict=True)
    topic: str
    position_a: str
    position_b: str
    resolution_test: str


class RiskItem(BaseModel):
    """A risk identified during council analysis."""

    model_config = ConfigDict(strict=True)
    name: str
    severity: int = Field(ge=1, le=10)
    probability: int = Field(ge=1, le=10)
    reversibility: int = Field(ge=1, le=10)
    score: int = 0
    description: str

    @model_validator(mode="after")
    def _compute_score(self) -> RiskItem:
        self.score = self.severity * self.probability * self.reversibility
        return self


class CriticalAssumption(BaseModel):
    """An assumption that must hold for the idea to succeed."""

    model_config = ConfigDict(strict=True)
    assumption: str
    why_critical: str
    evidence_strength: str
    evidence_summary: str


class ValidationExperiment(BaseModel):
    """A proposed experiment to validate a critical assumption."""

    model_config = ConfigDict(strict=True)
    name: str
    cost_estimate: str
    time_required: str
    success_criteria: str
    what_it_tests: str


class DebateSummary(BaseModel):
    """Council consensus, actionable improvements, and agreed weaknesses."""

    model_config = ConfigDict(strict=True)
    what_agents_agreed_on: list[str] = []
    what_would_strengthen_the_idea: list[str] = []
    key_disadvantages: list[str] = []


class SWOTAnalysis(BaseModel):
    """SWOT matrix grounded in collected data."""

    model_config = ConfigDict(strict=True)
    strengths: list[str] = []
    weaknesses: list[str] = []
    opportunities: list[str] = []
    threats: list[str] = []

    @model_validator(mode="after")
    def _validate_quadrants(self) -> SWOTAnalysis:
        for field_name in ("strengths", "weaknesses", "opportunities", "threats"):
            items = getattr(self, field_name)
            if items and len(items) < 2:
                raise ValueError(f"{field_name} must have at least 2 items if populated")
            if len(items) > 5:
                raise ValueError(f"{field_name} must have at most 5 items")
        return self


class CouncilAddendum(BaseModel):
    """Rare additional insight not covered elsewhere. Null by default."""

    model_config = ConfigDict(strict=True)
    topic: str
    insight: str
    raised_by: str


class AnalysisProfile(StrEnum):
    """Predefined analysis depth profiles."""

    EARLY_IDEA = "early_idea"
    PRE_LAUNCH = "pre_launch"
    PIVOT = "pivot"
    FULL = "full"


class AnalysisReport(BaseModel):
    """Final structured report from the AI Validation Council."""

    model_config = ConfigDict(strict=True)
    query: str
    divergence_report: list[DivergenceItem] = []
    risk_ranking: list[RiskItem] = []
    critical_assumptions: list[CriticalAssumption] = []
    validation_experiments: list[ValidationExperiment] = []
    confidence_score: float = 0.0
    confidence_interpretation: str = ""
    agent_outputs: list[dict] = []
    debate_summary: DebateSummary = Field(default_factory=DebateSummary)
    swot: SWOTAnalysis = Field(default_factory=SWOTAnalysis)
    addendum: CouncilAddendum | None = None
    counterfactual_triggered: bool = False
