"""Tests for ``council.config.resolve_llm_config`` and the LLM client's
input validation. Covers the bugs that produced empty-URL 401s and
empty-model retries in the original ``terminal.logs``.
"""

from __future__ import annotations

from typing import Any

import pytest

from council.config import (
    DEFAULT_BASE_URL,
    LLMRole,
    MissingLLMConfigError,
    ResolvedLLMConfig,
    get_settings_manager,
    resolve_llm_config,
)
from council.llm.client import (
    NON_RETRYABLE_STATUSES,
    AsyncLLMClient,
    _InvalidRequestError,
    _status_code_from_exception,
)


# Attribute names on Settings for each role's per-field config.
_ROLE_FIELDS: dict[LLMRole, dict[str, str]] = {
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


@pytest.fixture
def isolated_settings(tmp_path):
    """Snapshot of all per-role settings, mutated to a known state, restored
    on teardown. Also points the JSON persistence file at a tmp path so the
    user's real ``data/app_settings.json`` is untouched.
    """
    import council.config as cfg

    cfg.DEFAULT_SETTINGS_JSON = tmp_path / "app_settings.json"
    cfg._settings_manager = None
    cfg.settings = cfg.Settings()
    manager = cfg.get_settings_manager()  # builds singleton (re)loading JSON

    saved: dict[str, Any] = {}
    for role in LLMRole:
        for attr in _ROLE_FIELDS[role].values():
            saved[attr] = getattr(cfg.settings, attr, None)
    saved["llm_api_key"] = cfg.settings.llm_api_key

    def apply(overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            setattr(cfg.settings, key, value)

    yield apply

    for key, value in saved.items():
        setattr(cfg.settings, key, value)
    cfg._settings_manager = None


# ---------------------------------------------------------------------------
# resolve_llm_config
# ---------------------------------------------------------------------------


class TestResolveLLMConfig:
    def test_returns_resolved_object(self, isolated_settings):
        isolated_settings(
            {
                "market_analyst_model": "test-model",
                "market_analyst_base_url": "https://example.com/v1",
                "market_analyst_api_key": "test-key-123",
            }
        )

        resolved = resolve_llm_config(LLMRole.MARKET_ANALYST)

        assert resolved.model == "test-model"
        assert resolved.base_url == "https://example.com/v1"
        assert resolved.api_key == "test-key-123"
        assert resolved.role == LLMRole.MARKET_ANALYST
        assert resolved.is_complete() is True

    def test_falls_back_to_global_api_key(self, isolated_settings):
        isolated_settings(
            {
                "market_analyst_model": "model-x",
                "market_analyst_base_url": "https://x.com/v1",
                "market_analyst_api_key": None,
                "llm_api_key": "global-fallback-key",
            }
        )

        resolved = resolve_llm_config(LLMRole.MARKET_ANALYST)
        assert resolved.api_key == "global-fallback-key"

    def test_falls_back_to_default_base_url(self, isolated_settings):
        isolated_settings(
            {
                "report_model": "gpt-foo",
                "report_base_url": None,
                "report_api_key": "k",
                "llm_api_key": "k",
            }
        )

        resolved = resolve_llm_config(LLMRole.REPORT)
        assert resolved.base_url == DEFAULT_BASE_URL

    def test_falls_back_to_other_role_model(self, isolated_settings):
        """When the requested role has no model, fall back to another role's."""
        isolated_settings(
            {
                "devils_advocate_model": "fallback-model",
                "devils_advocate_base_url": "https://example.com/v1",
                "devils_advocate_api_key": "k",
                "report_model": "",
                "report_base_url": None,
                "report_api_key": None,
                "llm_api_key": "k",
            }
        )

        resolved = resolve_llm_config(LLMRole.REPORT)
        assert resolved.model == "fallback-model"
        assert resolved.role == LLMRole.REPORT

    def test_raises_when_no_api_key_anywhere(self, isolated_settings):
        isolated_settings(
            {
                "market_analyst_api_key": None,
                "llm_api_key": None,
                "market_analyst_model": "model",
                "market_analyst_base_url": "https://x.com/v1",
            }
        )

        with pytest.raises(MissingLLMConfigError) as exc:
            resolve_llm_config(LLMRole.MARKET_ANALYST)
        assert "API key" in str(exc.value)

    def test_raises_when_no_model_anywhere(self, isolated_settings):
        isolated_settings(
            {
                "market_analyst_model": "",
                "devils_advocate_model": "",
                "divergence_model": "",
                "report_model": "",
                "llm_api_key": "k",
            }
        )

        with pytest.raises(MissingLLMConfigError) as exc:
            resolve_llm_config(LLMRole.MARKET_ANALYST)
        assert "No model" in str(exc.value)

    def test_accepts_string_role(self, isolated_settings):
        isolated_settings(
            {
                "devils_advocate_model": "string-role-model",
                "devils_advocate_base_url": "https://x.com/v1",
                "devils_advocate_api_key": "k",
            }
        )

        resolved = resolve_llm_config("devils_advocate")
        assert resolved.role == LLMRole.DEVILS_ADVOCATE
        assert resolved.model == "string-role-model"

    def test_sees_json_persisted_settings(self, tmp_path):
        """Real-world scenario: user saves settings on the dashboard →
        they land in data/app_settings.json → next pipeline invocation
        must see them. This is the bug from terminal.logs line 76
        (empty model/base_url in the report call)."""
        import json
        import council.config as cfg

        cfg.DEFAULT_SETTINGS_JSON = tmp_path / "app_settings.json"
        # No global LLM_API_KEY, no per-role keys in JSON — but models + URLs
        # are persisted (non-secret fields).
        cfg.DEFAULT_SETTINGS_JSON.write_text(
            json.dumps(
                {
                    "market_analyst_model": "json-loaded-model",
                    "market_analyst_base_url": "https://from-json.test/v1",
                    "report_model": "json-report-model",
                    "report_base_url": "https://from-json.test/v1",
                }
            )
        )
        cfg._settings_manager = None
        cfg.settings = cfg.Settings()
        # No llm_api_key in .env either (it's `sk-...` placeholder), so we
        # need to provide one to make the resolver complete.
        cfg.settings.llm_api_key = "env-global-key"  # type: ignore[assignment]

        resolved = resolve_llm_config(LLMRole.MARKET_ANALYST)
        assert resolved.model == "json-loaded-model"
        assert resolved.base_url == "https://from-json.test/v1"
        assert resolved.api_key == "env-global-key"

        cfg._settings_manager = None


# ---------------------------------------------------------------------------
# LLM client input validation
# ---------------------------------------------------------------------------


class TestLLMClientValidation:
    def test_status_code_extraction(self):
        class FakeResponse:
            status_code = 401

        class FakeExc(Exception):
            response = FakeResponse()

        assert _status_code_from_exception(FakeExc()) == 401

    def test_status_code_returns_none_for_plain_exception(self):
        assert _status_code_from_exception(ValueError("x")) is None

    def test_non_retryable_statuses_include_auth_and_validation(self):
        assert 401 in NON_RETRYABLE_STATUSES
        assert 403 in NON_RETRYABLE_STATUSES
        assert 404 in NON_RETRYABLE_STATUSES
        assert 422 in NON_RETRYABLE_STATUSES
        assert 500 not in NON_RETRYABLE_STATUSES
        assert 502 not in NON_RETRYABLE_STATUSES

    @pytest.mark.asyncio
    async def test_empty_url_raises_missing_llm_config(self):
        """acompletion raises MissingLLMConfigError immediately on bad URL."""
        client = AsyncLLMClient()
        with pytest.raises(MissingLLMConfigError) as exc:
            await client.acompletion(
                model_key="m",
                messages=[{"role": "user", "content": "hi"}],
                base_url_override="",
                api_key_override="k",
            )
        assert "base_url" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_empty_api_key_raises_missing_llm_config(self):
        client = AsyncLLMClient()
        with pytest.raises(MissingLLMConfigError) as exc:
            await client.acompletion(
                model_key="m",
                messages=[{"role": "user", "content": "hi"}],
                base_url_override="https://x.com/v1",
                api_key_override="",
            )
        assert "API key" in str(exc.value)

    @pytest.mark.asyncio
    async def test_empty_model_raises_missing_llm_config(self):
        client = AsyncLLMClient()
        with pytest.raises(MissingLLMConfigError) as exc:
            await client.acompletion(
                model_key="",
                messages=[{"role": "user", "content": "hi"}],
                base_url_override="https://x.com/v1",
                api_key_override="k",
            )
        assert "model" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_request_does_not_retry(self):
        """Structural errors must NOT trigger the 3-attempt retry loop."""
        client = AsyncLLMClient()
        # If retries fired, this would block on asyncio.sleep. We use a small
        # timeout to make the test fast and fail-loud.
        import asyncio

        async def call():
            await asyncio.wait_for(
                client.acompletion(
                    model_key="",
                    messages=[{"role": "user", "content": "hi"}],
                    base_url_override="https://x.com/v1",
                    api_key_override="k",
                ),
                timeout=2.0,
            )

        with pytest.raises(MissingLLMConfigError):
            asyncio.run(call())

    @pytest.mark.asyncio
    async def test_non_retryable_status_does_not_retry(self, monkeypatch):
        """A 401 must not trigger 3 slow retries — fail fast.

        This is the bug from terminal.logs lines 10-15 where every auth
        failure did 3 retries with 5s/10s/20s backoff.
        """
        import httpx

        client = AsyncLLMClient()
        call_count = {"n": 0}

        class FakeResp:
            status_code = 401
            text = "Unauthorized"

            def raise_for_status(self) -> None:
                raise httpx.HTTPStatusError("401", request=None, response=self)

        class FakeAsyncClient:
            def __init__(self, *a, **kw) -> None: ...

            async def __aenter__(self) -> "FakeAsyncClient":
                return self

            async def __aexit__(self, *a) -> None: ...

            async def post(self, *a, **kw) -> FakeResp:
                call_count["n"] += 1
                return FakeResp()

        monkeypatch.setattr("council.llm.client.httpx.AsyncClient", FakeAsyncClient)

        with pytest.raises(httpx.HTTPStatusError):
            await client.acompletion(
                model_key="m",
                messages=[{"role": "user", "content": "hi"}],
                base_url_override="https://x.com/v1",
                api_key_override="k",
            )

        assert call_count["n"] == 1, (
            f"Expected 1 call on 401, got {call_count['n']} — "
            "client is retrying non-retryable statuses"
        )
