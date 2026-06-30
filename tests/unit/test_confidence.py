import pytest

from council.debate.confidence import (
    _count_verified_citations,
    calculate_confidence_score,
    compute_confidence_from_state,
    interpret_score,
)


class TestCalculateConfidenceScore:
    def test_max_score_with_ample_data_no_divergence(self):
        score = calculate_confidence_score(
            data_volume=200, divergence_count=0, source_diversity=5, recency_score=1.0
        )
        assert score == 80.0

    def test_divergence_penalty_reduces_score(self):
        score_no_div = calculate_confidence_score(data_volume=100, divergence_count=0)
        score_with_div = calculate_confidence_score(data_volume=100, divergence_count=4)
        assert score_with_div < score_no_div
        assert score_with_div == pytest.approx(score_no_div - 20, abs=0.1)

    def test_score_clamped_at_zero(self):
        score = calculate_confidence_score(
            data_volume=0, divergence_count=50, source_diversity=0, recency_score=0
        )
        assert score == 0.0

    def test_score_clamped_at_hundred(self):
        score = calculate_confidence_score(
            data_volume=1000, divergence_count=0, source_diversity=10, recency_score=5.0
        )
        assert score == 100.0

    def test_base_score_scales_with_data_volume(self):
        low = calculate_confidence_score(data_volume=10, divergence_count=0)
        high = calculate_confidence_score(data_volume=200, divergence_count=0)
        assert high > low

    def test_diversity_contributes_up_to_twenty(self):
        low_div = calculate_confidence_score(data_volume=100, source_diversity=1)
        high_div = calculate_confidence_score(data_volume=100, source_diversity=5)
        assert high_div == pytest.approx(low_div + 16, abs=1.0)


class TestComputeConfidenceFromState:
    def test_with_data_and_divergences(self, sample_reddit_posts, sample_hn_stories):
        state = {
            "reddit_posts": sample_reddit_posts,
            "hn_stories": sample_hn_stories,
            "divergence_points": [
                {"topic": "market_size"},
                {"topic": "pricing"},
            ],
        }
        score = compute_confidence_from_state(state)
        assert 0 <= score <= 30
        assert isinstance(score, float)
        assert score == round(score, 1)

    def test_empty_state(self):
        state = {"reddit_posts": [], "hn_stories": [], "divergence_points": []}
        score = compute_confidence_from_state(state)
        assert score < 20


class TestInterpretScore:
    def test_high_confidence(self):
        assert "High confidence" in interpret_score(85)

    def test_moderate_confidence(self):
        assert "Moderate confidence" in interpret_score(65)

    def test_low_confidence(self):
        assert "Low confidence" in interpret_score(45)

    def test_very_low_confidence(self):
        assert "Very low confidence" in interpret_score(25)

    def test_unreliable(self):
        assert "Unreliable" in interpret_score(5)


class TestCitationCounting:
    """Module 4: data_quality_factor depends on verified citation count."""

    def test_verified_citations_counted(self):
        outputs = [
            {
                "role": "market_analyst",
                "citation_checks": [
                    {"value": "a", "verified": True},
                    {"value": "b", "verified": False},
                    {"value": "c", "verified": True},
                ],
            }
        ]
        assert _count_verified_citations(outputs) == 2

    def test_hallucinated_citations_zero_data_quality(self):
        """5 hallucinated + 0 verified → no quality bonus from citations."""
        outputs = [
            {
                "role": "market_analyst",
                "citation_checks": [
                    {"value": f"https://fake-{i}.com", "verified": False} for i in range(5)
                ],
            }
        ]
        assert _count_verified_citations(outputs) == 0

    def test_legacy_fallback_when_citation_checks_absent(self):
        """Pre-Module-1 analyses used the bare ``citations`` list."""
        outputs = [{"role": "market_analyst", "citations": ["a", "b", "c"]}]
        assert _count_verified_citations(outputs) == 3

    def test_mixed_agents_citation_sum(self):
        outputs = [
            {
                "role": "market_analyst",
                "citation_checks": [{"value": "a", "verified": True}],
            },
            {
                "role": "devils_advocate",
                "citation_checks": [
                    {"value": "b", "verified": True},
                    {"value": "c", "verified": False},
                ],
            },
        ]
        assert _count_verified_citations(outputs) == 2


class TestDivergenceSanitization:
    """Module 4: divergence_count gated on parse status."""

    def test_parse_error_applies_max_penalty(self):
        """When divergence_status == 'parse_error', divergence is treated as
        large (max penalty). Score must drop vs. healthy parsed state with
        zero divergences."""
        healthy = {
            "reddit_posts": [],
            "hn_stories": [],
            "divergence_points": [],
            "divergence_status": "parsed",
        }
        broken = {
            "reddit_posts": [],
            "hn_stories": [],
            "divergence_points": [],
            "divergence_status": "parse_error",
        }
        assert compute_confidence_from_state(broken) < compute_confidence_from_state(healthy)

    def test_parsed_no_divergence_positive_quality(self):
        """3 verified citations + 0 divergence → positive score contribution."""
        state = {
            "reddit_posts": [],
            "hn_stories": [],
            "divergence_points": [],
            "divergence_status": "parsed",
            "agent_outputs": [
                {
                    "role": "market_analyst",
                    "citation_checks": [
                        {"value": f"https://verified-{i}.com", "verified": True} for i in range(3)
                    ],
                }
            ],
        }
        score_with_citations = compute_confidence_from_state(state)
        baseline_score = compute_confidence_from_state({**state, "agent_outputs": []})
        assert score_with_citations > baseline_score

    def test_parse_error_flagged_in_logs(self):
        import json

        from council.logging_config import logger

        captured: list[str] = []

        def sink(message: str) -> None:
            record = json.loads(message)
            captured.append(record["record"]["message"])

        handler_id = logger.add(sink, level="WARNING", serialize=True)
        try:
            state = {
                "reddit_posts": [],
                "hn_stories": [],
                "divergence_points": [],
                "divergence_status": "parse_error",
            }
            compute_confidence_from_state(state)
        finally:
            logger.remove(handler_id)

        joined = " ".join(captured)
        assert "divergence_status_parse_error" in joined
