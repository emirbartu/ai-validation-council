"""Tests for protocol improvements: anti-convergence, word limits, analysis profiles."""

from __future__ import annotations


class TestAntiConvergence:
    def test_agreement_ratio_low_no_trigger(self):
        from council.agents.council_graph import _compute_agreement_ratio

        outputs = [{"role": "ma", "content": "test"}, {"role": "da", "content": "test"}]
        divergence_points = [
            {
                "position_a": {"claim": "Market is growing 30%"},
                "position_b": {"claim": "Market is shrinking 5%"},
            },
            {
                "position_a": {"claim": "CAC is $50"},
                "position_b": {"claim": "CAC is $200"},
            },
        ]
        ratio = _compute_agreement_ratio(outputs, divergence_points)
        assert ratio < 0.70

    def test_agreement_ratio_high_triggers_counterfactual(self):
        from council.agents.council_graph import _compute_agreement_ratio

        outputs = [{"role": "ma", "content": "test"}, {"role": "da", "content": "test"}]
        divergence_points = [
            {
                "position_a": {"claim": "We agree market is growing"},
                "position_b": {"claim": "I concur, market growing"},
            },
            {
                "position_a": {"claim": "Both note same trend"},
                "position_b": {"claim": "Similar finding on pricing"},
            },
        ]
        ratio = _compute_agreement_ratio(outputs, divergence_points)
        assert ratio > 0.70

    def test_empty_divergence(self):
        from council.agents.council_graph import _compute_agreement_ratio

        assert _compute_agreement_ratio([], []) == 0.0


class TestWordLimits:
    def test_under_limit_unchanged(self):
        from council.agents.market_analyst import _enforce_word_limit

        text = "This is a short response."
        result = _enforce_word_limit(text, 0, "test_agent")
        assert result == text
        assert "..." not in result

    def test_over_limit_truncated(self):
        from council.agents.market_analyst import _enforce_word_limit

        text = "word " * 500  # 500 words
        result = _enforce_word_limit(text, 0, "test_agent")
        words = result.split()
        assert len(words) == 400  # 400 words, last one includes "..."
        assert result.endswith("...")

    def test_different_limits_per_round(self):
        from council.agents.market_analyst import _enforce_word_limit

        text = "word " * 500
        r0 = _enforce_word_limit(text, 0, "agent")
        r1 = _enforce_word_limit(text, 1, "agent")
        r2 = _enforce_word_limit(text, 2, "agent")
        assert len(r0.split()) == 400  # 400 words, last includes ...
        assert len(r1.split()) == 300  # 300 words, last includes ...
        assert len(r2.split()) == 150  # 150 words, last includes ...


class TestAnalysisProfile:
    def test_profile_enum_values(self):
        from council.models.report import AnalysisProfile

        assert AnalysisProfile.EARLY_IDEA.value == "early_idea"
        assert AnalysisProfile.FULL.value == "full"

    def test_profile_rounds(self):
        from council.agents.council_graph import PROFILE_ROUNDS

        assert PROFILE_ROUNDS["early_idea"] == 3
        assert PROFILE_ROUNDS["pre_launch"] == 2
        assert PROFILE_ROUNDS["pivot"] == 3
