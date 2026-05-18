"""Agent prompt loader and system prompt builder.

Reads SKILLS markdown files from the package's ``skills/`` directory and
assembles structured system prompts for council agents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from council.logging_config import logger


def _skills_dir() -> Path:
    """Return the absolute path to the ``src/council/skills`` directory."""
    return Path(__file__).resolve().parents[1] / "skills"


def load_skill_file(agent_name: str) -> str:
    """Read the SKILLS markdown file for *agent_name*.

    The file is expected at ``src/council/skills/{agent_name}.md``.
    Returns an empty string if the file does not exist.
    """
    path = _skills_dir() / f"{agent_name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("skills_file_not_found agent_name={} path={}", agent_name, path)
        return ""


def _format_reddit(post: dict[str, Any]) -> str:
    """Format a single Reddit post for the prompt context."""
    subreddit = post.get("subreddit", "unknown")
    score = post.get("score", 0)
    title = post.get("title", "")
    text = (post.get("text", "") or "")[:200]
    snippet = f" — {text}" if text else ""
    return f"r/{subreddit} | Score: {score} | {title}{snippet}"


def _format_hn(story: dict[str, Any]) -> str:
    """Format a single Hacker News story for the prompt context."""
    score = story.get("score", 0)
    title = story.get("title", "")
    text = (story.get("text") or "")[:200]
    snippet = f" — {text}" if text else ""
    return f"Score: {score} | {title}{snippet}"


def build_system_prompt(agent_name: str, query: str, context_data: dict[str, Any]) -> str:
    """Assemble a system prompt from the agent's SKILLS file and collected data.

    Parameters
    ----------
    agent_name:
        The kebab-case / snake_case agent identifier (e.g. ``market_analyst``).
    query:
        The user's original validation query.
    context_data:
        Dictionary containing ``reddit_posts``, ``hn_stories``, etc.
    """
    skills = load_skill_file(agent_name)

    reddit_posts = context_data.get("reddit_posts", [])
    hn_stories = context_data.get("hn_stories", [])

    reddit_lines = [_format_reddit(p) for p in reddit_posts] if reddit_posts else ["None"]
    hn_lines = [_format_hn(s) for s in hn_stories] if hn_stories else ["None"]

    reddit_block = "\n".join(f"  - {line}" for line in reddit_lines)
    hn_block = "\n".join(f"  - {line}" for line in hn_lines)

    return (
        f"{skills}\n"
        f"\n"
        f"--- ANALYSIS CONTEXT ---\n"
        f"USER QUERY: {query}\n"
        f"\n"
        f"COLLECTED MARKET DATA:\n"
        f"Reddit Results: {len(reddit_posts)} posts\n"
        f"{reddit_block}\n"
        f"\n"
        f"Hacker News Results: {len(hn_stories)} stories\n"
        f"{hn_block}\n"
        f"\n"
        f"--- END CONTEXT ---\n"
        f"\n"
        f"Produce your analysis following the format specified in your SKILLS file above.\n"
    )
