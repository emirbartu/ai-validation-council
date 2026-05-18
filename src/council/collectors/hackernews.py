"""Hacker News collector using Algolia Search API."""

from __future__ import annotations

import asyncio
from urllib.parse import quote

import httpx

from council.collectors.base import BaseCollector
from council.logging_config import logger
from council.models.data import HNStory


class HNCollector(BaseCollector[HNStory]):
    """Collect Hacker News stories via Algolia HN Search API."""

    name = "hackernews"
    _page_size = 100

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Initialize the collector.

        Args:
            client: Optional httpx.AsyncClient to use for requests.
        """
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def collect(self, query: str, max_results: int = 20) -> list[HNStory]:
        """Search HN for stories matching the query.

        Args:
            query: Search query string.
            max_results: Maximum number of stories to return.

        Returns:
            List of HNStory objects.
        """
        if not query.strip():
            logger.warning("HNCollector received empty query, returning empty list")
            return []

        stories: list[HNStory] = []
        pages_needed = (max_results + self._page_size - 1) // self._page_size

        for page in range(pages_needed):
            if page > 0 and max_results > self._page_size:
                await asyncio.sleep(1)

            url = (
                f"https://hn.algolia.com/api/v1/search?query={quote(query)}"
                f"&tags=story&hitsPerPage={self._page_size}&page={page}"
            )

            try:
                response = await self._client.get(url)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                logger.error(f"HNCollector HTTP error on page {page}: {exc}")
                break
            except Exception as exc:
                logger.error(f"HNCollector unexpected error on page {page}: {exc}")
                break

            hits = data.get("hits", [])
            if not hits:
                break

            for hit in hits:
                if len(stories) >= max_results:
                    break

                story = self._parse_hit(hit)
                if story is not None:
                    stories.append(story)

        logger.info(f"HNCollector found {len(stories)} stories for query '{query}'")
        return stories

    def _parse_hit(self, hit: dict) -> HNStory | None:
        """Parse a single Algolia hit into an HNStory.

        Args:
            hit: Raw hit dict from Algolia.

        Returns:
            HNStory or None if the hit should be filtered out.
        """
        points = hit.get("points", 0) or 0
        title = hit.get("title", "") or ""

        if points <= 0 or not title.strip():
            return None

        try:
            story_id = int(hit.get("objectID", 0))
        except (ValueError, TypeError):
            logger.warning(f"HNCollector skipping hit with invalid objectID: {hit.get('objectID')}")
            return None

        created_at_i = hit.get("created_at_i", 0) or 0

        return HNStory(
            id=story_id,
            title=title,
            text=hit.get("story_text"),
            score=points,
            url=hit.get("url"),
            by=hit.get("author", ""),
            time=int(created_at_i),
        )

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()
