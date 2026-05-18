"""Pydantic v2 models for agent provider and data provider configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, SecretStr


class AgentProviderConfig(BaseModel):
    """Per-agent LLM provider configuration."""

    model_config = ConfigDict(strict=True)

    model_name: str
    base_url: str | None = None
    api_key: SecretStr | None = None
    provider: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096

    def mask_api_key(self) -> str | None:
        """Return masked API key or None if not set."""
        if self.api_key is None:
            return None
        return "**********"


class DataProviderConfig(BaseModel):
    """Data source provider toggles."""

    model_config = ConfigDict(strict=True)

    reddit: bool = True
    hackernews: bool = True
    crawl4ai: bool = False
