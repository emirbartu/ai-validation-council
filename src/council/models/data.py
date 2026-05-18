"""Pydantic v2 models for collected data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RedditPost(BaseModel):
    """A single Reddit post collected during data gathering."""

    model_config = ConfigDict(strict=True)

    id: str
    title: str
    text: str
    subreddit: str
    score: int
    url: str
    created_utc: float


class HNStory(BaseModel):
    """A single Hacker News story collected during data gathering."""

    model_config = ConfigDict(strict=True)

    id: int
    title: str
    text: str | None
    score: int
    url: str | None
    by: str
    time: int


class CollectedData(BaseModel):
    """Aggregated data from all collectors."""

    model_config = ConfigDict(strict=True)

    reddit_posts: list[RedditPost]
    hn_stories: list[HNStory]
    crawl_results: list[Any] = []
