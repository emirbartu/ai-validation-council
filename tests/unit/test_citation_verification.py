"""Citation verification against collected source data.

Module 1 contract:
- Real Reddit permalinks → verified: True
- Real HN discussion URLs (item?id=...) → verified: True
- Real HN external URLs → verified: True
- Hallucinated URLs → verified: False
- Text citations matching collected titles → verified: True
- Text citations with no match → verified: False
"""

from __future__ import annotations

from council.debate.citation_verification import verify_citations

SAMPLE_REDDIT = [
    {
        "id": "abc123",
        "title": "AI for dental practice management",
        "url": "https://reddit.com/r/Dentistry/comments/abc123/",
    },
    {
        "id": "def456",
        "title": "Patient follow-up CRM suggestions",
        "url": "https://reddit.com/r/smallbusiness/comments/def456/",
    },
]

SAMPLE_HN = [
    {
        "id": 40012345,
        "title": "AI-Driven Dental Practice Management Raises $20M Series A",
        "url": "https://techcrunch.com/2026/05/dental-ai-funding/",
        "by": "techfounder",
    },
    {
        "id": 40012346,
        "title": "Show HN: Open-source patient scheduling tool",
        "url": None,
        "by": "indiehacker",
    },
]


class TestRedditCitationVerification:
    def test_real_reddit_permalink_verified(self):
        raw = ["https://reddit.com/r/Dentistry/comments/abc123/"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert len(result) == 1
        assert result[0]["verified"] is True
        assert result[0]["source_type"] == "reddit"
        assert result[0]["matched_title"] == "AI for dental practice management"

    def test_reddit_text_mention_verified(self):
        raw = ["AI for dental practice management"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert len(result) == 1
        assert result[0]["verified"] is True
        assert result[0]["source_type"] == "reddit"


class TestHNCitationVerification:
    def test_hn_discussion_url_verified(self):
        raw = ["https://news.ycombinator.com/item?id=40012345"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert len(result) == 1
        assert result[0]["verified"] is True
        assert result[0]["source_type"] == "hackernews"
        assert "AI-Driven Dental Practice Management" in result[0]["matched_title"]

    def test_hn_external_url_verified(self):
        raw = ["https://techcrunch.com/2026/05/dental-ai-funding/"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert len(result) == 1
        assert result[0]["verified"] is True
        assert result[0]["source_type"] == "hackernews"

    def test_hn_text_mention_verified(self):
        raw = ["Show HN: Open-source patient scheduling tool"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert len(result) == 1
        assert result[0]["verified"] is True
        assert result[0]["source_type"] == "hackernews"


class TestHallucinatedCitations:
    def test_hallucinated_url_unverified(self):
        raw = ["https://techcrunch.com/fake-article-does-not-exist"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert len(result) == 1
        assert result[0]["verified"] is False
        assert result[0]["source_type"] is None
        assert result[0]["matched_title"] is None

    def test_hallucinated_subreddit_url_unverified(self):
        raw = ["https://reddit.com/r/Nonexistent/comments/zzz999/"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert result[0]["verified"] is False

    def test_text_with_no_match_unverified(self):
        raw = ["Source: Blockbuster pivot to streaming 2026 research"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert result[0]["verified"] is False
        assert result[0]["source_type"] is None


class TestOutputSchema:
    def test_output_keys(self):
        raw = ["https://reddit.com/r/Dentistry/comments/abc123/"]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert set(result[0].keys()) == {
            "value",
            "verified",
            "source_type",
            "matched_title",
        }

    def test_preserves_stripped_value(self):
        raw = ["  https://reddit.com/r/Dentistry/comments/abc123/  "]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert result[0]["value"] == "https://reddit.com/r/Dentistry/comments/abc123/"

    def test_empty_input_returns_empty(self):
        assert verify_citations([], SAMPLE_REDDIT, SAMPLE_HN) == []

    def test_mixed_real_and_hallucinated(self):
        raw = [
            "https://reddit.com/r/Dentistry/comments/abc123/",
            "https://techcrunch.com/fake-article",
            "AI for dental practice management",
            "Source: Underwater basket weaving trends",
        ]
        result = verify_citations(raw, SAMPLE_REDDIT, SAMPLE_HN)
        assert result[0]["verified"] is True
        assert result[1]["verified"] is False
        assert result[2]["verified"] is True
        assert result[3]["verified"] is False
