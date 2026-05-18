from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WebPage(BaseModel):
    model_config = ConfigDict(strict=True)
    url: str = Field(description="Source URL")
    title: str = Field(default="", description="Page title")
    markdown: str = Field(default="", description="Extracted markdown content")
    snippet: str = Field(default="", description="First 500 chars of content")
    success: bool = Field(default=True)
    error: str | None = Field(default=None)
