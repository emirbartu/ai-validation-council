from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from council.logging_config import logger
from council.models.provider_config import AgentProviderConfig, DataProviderConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    llm_api_key: SecretStr | None = None
    serper_api_key: SecretStr | None = None
    database_url: str | None = None
    redis_url: str | None = None
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    mempalace_path: str | None = None
    max_analyses_per_user_per_day: int = 5
    max_concurrent_analyses: int = 3
    llm_daily_limit: float = 50.0

    market_analyst_model: str = ""
    market_analyst_base_url: str | None = None
    market_analyst_api_key: SecretStr | None = None
    market_analyst_provider: str = ""

    devils_advocate_model: str = ""
    devils_advocate_base_url: str | None = None
    devils_advocate_api_key: SecretStr | None = None
    devils_advocate_provider: str = ""

    divergence_model: str = ""
    divergence_base_url: str | None = None
    divergence_api_key: SecretStr | None = None
    divergence_provider: str = ""

    report_model: str = ""
    report_base_url: str | None = None
    report_api_key: SecretStr | None = None
    report_provider: str = ""

    enable_reddit: bool = True
    enable_hackernews: bool = True
    enable_crawl4ai: bool = False


DEFAULT_SETTINGS_JSON = (
    Path(__file__).resolve().parent.parent.parent / "data" / "app_settings.json"
)

_SECRET_FIELDS = {
    "serper_api_key",
    "qdrant_api_key",
    "market_analyst_api_key",
    "devils_advocate_api_key",
    "divergence_api_key",
    "report_api_key",
}

SAFE_PERSIST_FIELDS = {
    "market_analyst_model",
    "market_analyst_base_url",
    "devils_advocate_model",
    "devils_advocate_base_url",
    "divergence_model",
    "divergence_base_url",
    "report_model",
    "report_base_url",
    "report_provider",
    "market_analyst_provider",
    "devils_advocate_provider",
    "divergence_provider",
    "enable_reddit",
    "enable_hackernews",
    "enable_crawl4ai",
    "log_level",
}

settings = Settings()


def get_settings() -> Settings:
    """Return the module-level Settings instance."""
    return settings


class SettingsManager:
    """Manages application settings with hot reload and secret masking."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._load_from_json()

    def _coerce_value(self, key: str, value: Any) -> Any:
        if key in _SECRET_FIELDS and value is not None:
            return SecretStr(str(value))
        return value

    def _persist_settings(self) -> None:
        DEFAULT_SETTINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
        safe_data = {
            k: v
            for k, v in self._settings.model_dump().items()
            if k in SAFE_PERSIST_FIELDS and v is not None
        }
        with open(DEFAULT_SETTINGS_JSON, "w", encoding="utf-8") as f:
            json.dump(safe_data, f, indent=2, default=str)

    def _load_from_json(self) -> None:
        if not DEFAULT_SETTINGS_JSON.exists():
            return
        try:
            with open(DEFAULT_SETTINGS_JSON, encoding="utf-8") as f:
                overrides = json.load(f)
            for key, value in overrides.items():
                if (
                    key in SAFE_PERSIST_FIELDS
                    and hasattr(self._settings, key)
                    and value is not None
                ):
                    setattr(self._settings, key, self._coerce_value(key, value))
        except Exception as exc:
            logger.warning("Failed to load persisted settings: {}", exc)

    def mask_secrets(self) -> dict:
        """Return a dict representation of settings with secrets masked."""
        raw = self._settings.model_dump()
        for key in _SECRET_FIELDS:
            if raw.get(key) is not None:
                raw[key] = "**********"
        return raw

    def reload(self) -> None:
        """Reload settings by re-reading the .env file."""
        global settings
        settings = Settings()
        self._settings = settings
        self._load_from_json()
        logger.info("Settings reloaded from .env")

    def apply_update(self, updates: dict) -> dict:
        changed = {}
        for key, value in updates.items():
            if value is None or not hasattr(self._settings, key):
                continue
            if key in _SECRET_FIELDS and str(value) == "**********":
                continue
            setattr(self._settings, key, self._coerce_value(key, value))
            changed[key] = value
        if changed:
            self._persist_settings()
        return changed

    def get_app_config(self) -> dict[str, AgentProviderConfig | DataProviderConfig]:
        """Return AgentProviderConfig instances for each agent from Settings fields."""
        return {
            "market_analyst": AgentProviderConfig(
                model_name=self._settings.market_analyst_model,
                base_url=self._settings.market_analyst_base_url,
                api_key=self._settings.market_analyst_api_key,
                provider=self._settings.market_analyst_provider,
            ),
            "devils_advocate": AgentProviderConfig(
                model_name=self._settings.devils_advocate_model,
                base_url=self._settings.devils_advocate_base_url,
                api_key=self._settings.devils_advocate_api_key,
                provider=self._settings.devils_advocate_provider,
            ),
            "divergence_detector": AgentProviderConfig(
                model_name=self._settings.divergence_model,
                base_url=self._settings.divergence_base_url,
                api_key=self._settings.divergence_api_key,
                provider=self._settings.divergence_provider,
            ),
            "report": AgentProviderConfig(
                model_name=self._settings.report_model,
                base_url=self._settings.report_base_url,
                api_key=self._settings.report_api_key,
                provider=self._settings.report_provider,
            ),
            "data_providers": DataProviderConfig(
                reddit=self._settings.enable_reddit,
                hackernews=self._settings.enable_hackernews,
                crawl4ai=self._settings.enable_crawl4ai,
            ),
        }


_settings_manager: SettingsManager | None = None


def get_settings_manager() -> SettingsManager:
    """Return the module-level SettingsManager singleton."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
