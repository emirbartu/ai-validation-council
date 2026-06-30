"""Reddit data collector via Serper API."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger

from council.collectors.base import BaseCollector
from council.config import settings
from council.models.data import RedditPost

_SUBREDDIT_PATTERN = re.compile(r"/r/(?P<subreddit>[^/]+)")
_POST_ID_PATTERN = re.compile(r"/comments/(?P<post_id>[^/]+)")


def _extract_subreddit(url: str) -> str | None:
    match = _SUBREDDIT_PATTERN.search(url)
    return match.group("subreddit") if match else None


def _extract_post_id(url: str) -> str | None:
    match = _POST_ID_PATTERN.search(url)
    return match.group("post_id") if match else None


def _parse_date(date_str: str | None) -> float:
    if not date_str:
        return 0.0
    formats = (
        "%b %d, %Y",
        "%d %b %Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=UTC).timestamp()
        except ValueError:
            continue
    return 0.0


def _result_to_post(result: dict[str, Any]) -> RedditPost | None:
    url = result.get("link", "")
    if not url:
        return None

    subreddit = _extract_subreddit(url)
    post_id = _extract_post_id(url)
    if not subreddit or not post_id:
        logger.debug(f"Skipping non-Reddit result: {url}")
        return None

    return RedditPost(
        id=post_id,
        title=result.get("title", ""),
        text=result.get("snippet", ""),
        subreddit=subreddit,
        score=0,
        url=url,
        created_utc=_parse_date(result.get("date")),
    )


class RedditCollector(BaseCollector[RedditPost]):
    """Collect Reddit posts using the Serper Google Search API.

    Searches are scoped to ``site:reddit.com`` so that only Reddit results are
    returned. Each organic result is mapped to a :class:`~council.models.data.RedditPost`.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._base_url = "https://google.serper.dev/search"
        self._max_retries = 3

    async def collect(self, query: str, max_results: int = 20) -> list[RedditPost]:
        api_key = settings.serper_api_key
        if api_key is None or (
            hasattr(api_key, "get_secret_value") and not api_key.get_secret_value()
        ):
            logger.warning("SERPER_API_KEY is not configured, skipping Reddit collection")
            return []

        payload = {
            "q": f"site:reddit.com {query}",
            "num": max_results,
        }
        headers = {
            "X-API-KEY": api_key.get_secret_value(),
            "Content-Type": "application/json",
        }

        response: httpx.Response | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._client.post(
                    self._base_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < self._max_retries:
                    logger.warning(
                        f"Serper API rate limited (429), waiting 1s before retry "
                        f"(attempt {attempt}/{self._max_retries})",
                    )
                    await asyncio.sleep(1.0)
                    continue
                logger.error(f"Serper API request failed: {exc}")
                return []
            except httpx.HTTPError as exc:
                logger.error(f"HTTP error contacting Serper API: {exc}")
                return []

        if response is None:
            logger.error("No response received from Serper API")
            return []

        try:
            data = response.json()
        except ValueError as exc:
            logger.error(f"Failed to parse Serper API response: {exc}")
            return []

        organic_results = data.get("organic", [])
        if not organic_results:
            logger.warning(f"No organic results for query: {query}")
            return []

        posts: list[RedditPost] = []
        for result in organic_results:
            post = _result_to_post(result)
            if post is not None:
                posts.append(post)

        logger.info(f"Collected {len(posts)} Reddit posts for query: {query}")
        return posts
