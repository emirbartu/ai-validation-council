"""Test the Devil's Advocate forbidden phrase validator.

This is critical — it's the anti-sycophancy enforcement mechanism.
"""

from council.agents.devils_advocate import check_forbidden_phrases


class TestCheckForbiddenPhrases:
    def test_clean_response_passes(self):
        response = (
            "This market has 3 entrenched competitors. "
            "CAC at $150 per keyword click is unsustainable at $50 ARPU. "
            "The fatal assumption is that dentists will switch from incumbent software."
        )
        has_forbidden, detected = check_forbidden_phrases(response)
        assert not has_forbidden
        assert len(detected) == 0

    def test_detects_with_the_right_team(self):
        response = "The idea faces competition, but with the right team it could succeed."
        has_forbidden, detected = check_forbidden_phrases(response)
        assert has_forbidden
        assert any("with the right" in d.lower() for d in detected)

    def test_detects_with_the_right_execution(self):
        response = "With the right execution strategy, this idea might capture market share."
        has_forbidden, detected = check_forbidden_phrases(response)
        assert has_forbidden

    def test_detects_promising_concept(self):
        response = "This is a promising concept that addresses a real need."
        has_forbidden, detected = check_forbidden_phrases(response)
        assert has_forbidden

    def test_detects_there_is_potential_if(self):
        response = (
            "There is potential if they work with the right partners. "
            "However, existing data suggests otherwise."
        )
        has_forbidden, detected = check_forbidden_phrases(response)
        assert has_forbidden

    def test_detects_encouraging_closing_sentence(self):
        response = (
            "Competition is fierce. CAC is high. "
            "But the dental software market has great potential."
        )
        has_forbidden, detected = check_forbidden_phrases(response)
        assert has_forbidden
        assert any("encouraging" in d.lower() for d in detected)

    def test_detects_however_with_positive_sentiment(self):
        response = (
            "The market is crowded. However, there is a clear opportunity "
            "for a modern, AI-first solution."
        )
        has_forbidden, detected = check_forbidden_phrases(response)
        assert has_forbidden

    def test_detects_idea_has_merit(self):
        response = "The idea has merit, but faces significant execution challenges."
        has_forbidden, detected = check_forbidden_phrases(response)
        assert has_forbidden

    def test_detects_while_challenges_exist(self):
        response = (
            "While challenges exist, the market opportunity could justify the risk. "
            "However with the right execution this startup might capture share."
        )
        has_forbidden, detected = check_forbidden_phrases(response)
        assert has_forbidden

    def test_harsh_valid_response_passes(self):
        response = (
            "This idea will fail. Kill Shot 1: Unit Economics — CAC of $500 vs ARPU of $50 "
            "means a 10-month payback period on a market with 30% annual churn. "
            "THE FATAL ASSUMPTION: This idea requires dentists to switch from software "
            "they've used for 15 years. The data shows 3% annual churn in dental PMS."
        )
        has_forbidden, detected = check_forbidden_phrases(response)
        assert not has_forbidden
