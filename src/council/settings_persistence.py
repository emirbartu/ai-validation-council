"""JSON persistence for runtime app configuration with atomic writes."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from council.logging_config import logger
from council.models.provider_config import AgentProviderConfig, DataProviderConfig

DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "settings.json"


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_app_config(
    path: Path | str | None = None,
) -> dict[str, AgentProviderConfig | DataProviderConfig]:
    """Load persisted app configuration from JSON.

    Returns a dict mapping agent names to ``AgentProviderConfig`` instances,
    plus a ``data_providers`` key with a ``DataProviderConfig``. Falls back
    to sensible defaults on parse failure or missing file.
    """
    target = Path(path) if path else DEFAULT_SETTINGS_PATH

    if not target.exists():
        logger.info("No persisted settings found at {}, using defaults", target)
        return _default_app_config()

    try:
        with open(target, encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Failed to load settings from {}: {}, using defaults",
            target,
            exc,
        )
        return _default_app_config()

    try:
        agents: dict[str, AgentProviderConfig] = {}
        for key in ("market_analyst", "devils_advocate", "divergence_detector", "report"):
            if key in raw.get("agents", {}):
                agents[key] = AgentProviderConfig.model_validate(raw["agents"][key])
            else:
                agents[key] = _default_agent_config(key)

        data_providers = DataProviderConfig.model_validate(
            raw.get("data_providers", {}),
        )
    except Exception as exc:
        logger.warning(
            "Invalid settings format in {}: {}, using defaults",
            target,
            exc,
        )
        return _default_app_config()

    return {
        **agents,
        "data_providers": data_providers,
    }


def save_app_config(
    config: dict[str, AgentProviderConfig | DataProviderConfig],
    path: Path | str | None = None,
) -> None:
    """Save app configuration to JSON using an atomic temp-file + rename."""
    target = Path(path) if path else DEFAULT_SETTINGS_PATH
    _ensure_dir(target)

    payload: dict[str, dict] = {"agents": {}, "data_providers": {}}
    for key, value in config.items():
        if key == "data_providers" and isinstance(value, DataProviderConfig):
            payload["data_providers"] = value.model_dump()
        elif isinstance(value, AgentProviderConfig):
            payload["agents"][key] = value.model_dump()

    fd, temp_path = tempfile.mkstemp(dir=target.parent, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        os.replace(temp_path, target)
        logger.info("Settings saved atomically to {}", target)
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(temp_path)
        raise


def _default_agent_config(agent_name: str) -> AgentProviderConfig:
    return AgentProviderConfig(model_name="", provider="")


def _default_app_config() -> dict[str, AgentProviderConfig | DataProviderConfig]:
    return {
        "market_analyst": _default_agent_config("market_analyst"),
        "devils_advocate": _default_agent_config("devils_advocate"),
        "divergence_detector": _default_agent_config("divergence_detector"),
        "report": _default_agent_config("report"),
        "data_providers": DataProviderConfig(),
    }
