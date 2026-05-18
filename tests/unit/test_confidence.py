import pytest

from council.debate.confidence import (
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
