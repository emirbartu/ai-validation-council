"""Citation verification against collected source data.

Agent outputs cite sources as free text or URLs. This module checks each
extracted citation against the actual collected Reddit/HN data so that only
citations traceable to real, retrieved data count toward `citations` and the
confidence score's data_quality_factor. Citations that cannot be matched are
not deleted -- they are kept in `citation_checks` for visibility but excluded
from the verified `citations` list.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse


def _normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url.strip().rstrip("/").lower()

    scheme = "https"

    netloc = parsed.netloc.lower().removeprefix("www.")

    path = parsed.path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", "", ""))


def _build_lookup(
    reddit_posts: list[dict[str, Any]],
    hn_stories: list[dict[str, Any]],
) -> dict[str, tuple[str, str, dict[str, Any]]]:
    lookup: dict[str, tuple[str, str, dict[str, Any]]] = {}

    for post in reddit_posts:
        # RedditPost model: id, title, text, subreddit, score, url, created_utc
        url = post.get("url", "")
        if not url:
            continue

        norm = _normalize_url(url)

        lookup[norm] = ("reddit", post.get("title", ""), post)

        for subdomain in ("i.", "old.", "np.", "amp."):
            mobile_url = url.replace("://www.", "://").replace("://", f"://{subdomain}")
            lookup[_normalize_url(mobile_url)] = ("reddit", post.get("title", ""), post)
    for story in hn_stories:
        # HNStory model: id, title, text, score, url, by, time

        story_id = story.get("id")
        title = story.get("title", "")

        # HN discussion URLs differ only by `?id=N` — _normalize_url drops
        # query strings, so all HN item pages collapse to the same key. Use
        # the raw URL as the lookup key (without normalization) so each
        # story gets its own entry.
        if story_id is not None:
            discussion_key = f"https://news.ycombinator.com/item?id={story_id}"
            lookup[discussion_key] = ("hackernews", title, story)

        external_url = story.get("url")
        if external_url:
            lookup[_normalize_url(external_url)] = ("hackernews", title, story)

    return lookup


def verify_citations(
    raw_citations: list[str],
    reddit_posts: list[dict[str, Any]],
    hn_stories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = _build_lookup(reddit_posts, hn_stories)

    results: list[dict[str, Any]] = []

    for citation in raw_citations:
        citation = citation.strip()
        if not citation:
            continue

        if citation.startswith(("http://", "https://")):
            norm = _normalize_url(citation)
            # Also try the raw (non-normalized) form so HN item?id=... URLs
            # can match the un-normalized key stored in the lookup.
            candidates = {norm, citation.strip()}

            matched_entry = None
            for key in candidates:
                if key in lookup:
                    matched_entry = lookup[key]
                    break

            if matched_entry is not None:
                source_type, title, _ = matched_entry
                results.append(
                    {
                        "value": citation,
                        "verified": True,
                        "source_type": source_type,
                        "matched_title": title,
                    }
                )
            else:
                results.append(
                    {
                        "value": citation,
                        "verified": False,
                        "source_type": None,
                        "matched_title": None,
                    }
                )

        else:
            matched = False
            matched_title: str | None = None
            matched_type: str | None = None

            for post in reddit_posts:
                title = post.get("title", "")
                if citation.lower() in title.lower() or title.lower() in citation.lower():
                    matched = True
                    matched_title = title
                    matched_type = "reddit"
                    break

            if not matched:
                for story in hn_stories:
                    title = story.get("title", "")
                    if citation.lower() in title.lower() or title.lower() in citation.lower():
                        matched = True
                        matched_title = title
                        matched_type = "hackernews"
                        break

            results.append(
                {
                    "value": citation,
                    "verified": matched,
                    "source_type": matched_type,
                    "matched_title": matched_title,
                }
            )

    return results
