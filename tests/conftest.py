import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


@pytest.fixture
def sample_reddit_posts():
    return [
        {
            "id": "abc123",
            "title": "Is anyone using AI for dental practice management?",
            "text": "We spend 15 hours a week on manual scheduling and billing...",
            "subreddit": "Dentistry",
            "score": 42,
            "url": "https://reddit.com/r/Dentistry/comments/abc123/",
            "created_utc": 1714867200.0,
        },
        {
            "id": "def456",
            "title": "Looking for CRM that handles patient follow-ups automatically",
            "text": "Our office has 12 dentists and tracking follow-ups is a nightmare...",
            "subreddit": "smallbusiness",
            "score": 89,
            "url": "https://reddit.com/r/smallbusiness/comments/def456/",
            "created_utc": 1714953600.0,
        },
    ]


@pytest.fixture
def sample_hn_stories():
    return [
        {
            "id": 40012345,
            "title": "AI-Driven Dental Practice Management Raises $20M Series A",
            "text": None,
            "score": 156,
            "url": "https://techcrunch.com/2026/05/dental-ai-funding/",
            "by": "techfounder",
            "time": 1714953600,
        },
    ]


@pytest.fixture
def sample_agent_outputs():
    return [
        {
            "role": "market_analyst",
            "content": "TAM: $12B. The dental practice management market is growing at 8.4% CAGR.",
            "citations": ["https://grandviewresearch.com/dental-practice-management"],
            "confidence": 0.0,
        },
        {
            "role": "devils_advocate",
            "content": "Kill Shot 1: Market Kill Shot — The dental software market has 3 dominant players with $50M+ revenue each. This startup has zero distribution in a relationship-driven industry. Data: Dentrix (35% share), Eaglesoft (28%), OpenDental (18%).",
            "kill_shots": [
                {"title": "Entrenched Competitors", "reasoning": "3 dominant players with 81% combined market share", "data_point": "Dentrix: 35%, Eaglesoft: 28%, OpenDental: 18%"}
            ],
            "verdict": "This idea dies from entrenched competition and high switching costs.",
            "forbidden_check_passed": True,
            "retry_attempted": False,
            "confidence": 0.0,
        },
    ]


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.achat = AsyncMock()
    return client
