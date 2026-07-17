from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from council.logging_config import logger
from council.models.provider_config import AgentProviderConfig, DataProviderConfig


class LLMRole(StrEnum):
    MARKET_ANALYST = "market_analyst"
    DEVILS_ADVOCATE = "devils_advocate"
    DIVERGENCE = "divergence"
    REPORT = "report"


class MissingLLMConfigError(RuntimeError):
    """Raised when an agent role has no usable model + key + base_url combo."""


@dataclass(frozen=True)
class ResolvedLLMConfig:
    """Concrete (model, base_url, api_key) tuple for an LLM call.

    Returned by ``resolve_llm_config``. All three fields are guaranteed
    non-empty when this object is constructed; callers may pass them
    straight to the LLM client without further checks.
    """

    role: LLMRole
    model: str
    base_url: str
    api_key: str

    def is_complete(self) -> bool:
        return bool(self.model) and bool(self.base_url) and bool(self.api_key)

# Default base URL when no per-agent value is configured.
# OpenRouter is the most common provider observed in production logs.
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def _secret_value(secret: SecretStr | str | None) -> str:
    if secret is None:
        return ""
    if isinstance(secret, SecretStr):
        try:
            return secret.get_secret_value()
        except Exception:
            return ""
    if isinstance(secret, str):
        return secret
    return str(secret)


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


DEFAULT_SETTINGS_JSON = Path(__file__).resolve().parent.parent.parent / "data" / "app_settings.json"

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

# Per-role attribute mapping. Used by ``resolve_llm_config`` to read the
# matching settings fields. Order does not matter; the resolver handles
# fallbacks.
_ROLE_ATTRS: dict[LLMRole, dict[str, str]] = {
    LLMRole.MARKET_ANALYST: {
        "model": "market_analyst_model",
        "base_url": "market_analyst_base_url",
        "api_key": "market_analyst_api_key",
    },
    LLMRole.DEVILS_ADVOCATE: {
        "model": "devils_advocate_model",
        "base_url": "devils_advocate_base_url",
        "api_key": "devils_advocate_api_key",
    },
    LLMRole.DIVERGENCE: {
        "model": "divergence_model",
        "base_url": "divergence_base_url",
        "api_key": "divergence_api_key",
    },
    LLMRole.REPORT: {
        "model": "report_model",
        "base_url": "report_base_url",
        "api_key": "report_api_key",
    },
}

# Fallback chain (in order) for `model` when the per-role value is empty.
# Devil's Advocate first because it's a deterministic, structurally
# validated agent that's always required.
_MODEL_FALLBACK_CHAIN: tuple[LLMRole, ...] = (
    LLMRole.DEVILS_ADVOCATE,
    LLMRole.MARKET_ANALYST,
    LLMRole.DIVERGENCE,
    LLMRole.REPORT,
)


def _read_role_value(role: LLMRole, kind: str, s: Settings) -> str:
    attr = _ROLE_ATTRS[role].get(kind)
    if attr is None:
        return ""
    raw = getattr(s, attr, None)
    if raw is None:
        return ""
    if isinstance(raw, SecretStr):
        return _secret_value(raw)
    if isinstance(raw, str):
        return raw.strip()
    return str(raw).strip()


def resolve_llm_config(role: LLMRole | str) -> ResolvedLLMConfig:
    """Resolve the effective ``(model, base_url, api_key)`` for a role.

    Priority for each field (highest first):

    1. Per-role value from settings (set via dashboard or ``.env``).
    2. Global ``LLM_API_KEY`` for ``api_key`` only.
    3. ``DEFAULT_BASE_URL`` for ``base_url`` only.
    4. Per-role model falls back to other roles' models in the chain
       (Devil's Advocate → Market Analyst → Divergence → Report).

    Raises ``MissingLLMConfigError`` if no model + api_key combination can
    be resolved. The returned object is always complete — empty values
    never escape this function.

    Always consults ``get_settings_manager()`` first so JSON-stored
    settings (set via the dashboard) are visible — module-level
    ``settings`` only sees ``.env`` until the manager loads JSON.
    """
    if isinstance(role, str):
        role = LLMRole(role)

    # Force manager construction (loads JSON on first call).
    s = get_settings_manager()._settings

    model = _read_role_value(role, "model", s)
    base_url = _read_role_value(role, "base_url", s)
    api_key = _read_role_value(role, "api_key", s)

    if not api_key:
        api_key = _secret_value(s.llm_api_key)

    if not model:
        for fallback_role in _MODEL_FALLBACK_CHAIN:
            if fallback_role == role:
                continue
            fallback_model = _read_role_value(fallback_role, "model", s)
            if fallback_model:
                model = fallback_model
                logger.warning(
                    "llm_config_model_fallback role={} using={}",
                    role.value,
                    fallback_role.value,
                )
                break

    if not base_url:
        base_url = DEFAULT_BASE_URL
        logger.warning(
            "llm_config_base_url_defaulted role={} base_url={}",
            role.value,
            base_url,
        )

    if not api_key:
        raise MissingLLMConfigError(
            f"No API key configured for {role.value}. "
            "Set it on the Settings page (per-agent) or set LLM_API_KEY in .env.",
        )
    if not model:
        raise MissingLLMConfigError(
            f"No model configured for {role.value} (and no fallback model "
            "from other agents). Set a model on the Settings page or in .env.",
        )

    return ResolvedLLMConfig(
        role=role,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )


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
