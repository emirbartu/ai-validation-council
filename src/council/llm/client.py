"""OpenAI-compatible async LLM client with retry and cost tracking."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import httpx

from council.config import MissingLLMConfigError, get_settings
from council.logging_config import get_trace_id, logger

RETRY_DELAYS = [5.0, 10.0, 20.0]

# HTTP statuses that mean "the request is fundamentally broken" — retrying
# won't help. Skip the retry backoff and surface the error immediately.
# 401: bad/expired key · 403: forbidden (often bad scope/revoked key)
# 404: wrong base_url · 422: model rejected our schema
NON_RETRYABLE_STATUSES = {401, 403, 404, 422}


def _status_code_from_exception(exc: BaseException) -> int | None:
    """Pull the HTTP status code off an httpx exception, if any."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    code = getattr(response, "status_code", None)
    if code is None:
        return None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


class _InvalidRequestError(ValueError):
    """Raised when the LLM call is structurally invalid before it goes out.

    Caller code (agent / divergence / report) should propagate this up so
    the pipeline sees a clean ``MissingLLMConfigError`` or
    ``report_extraction_failed`` instead of three slow retries against an
    empty URL.
    """


class _FakeResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def usage(self) -> Any:
        u = self._data.get("usage", {})
        return type(
            "Usage",
            (),
            {
                "prompt_tokens": u.get("prompt_tokens", 0),
                "completion_tokens": u.get("completion_tokens", 0),
            },
        )

    @property
    def choices(self) -> list[dict[str, Any]]:
        return self._data.get("choices", [])

    def model_dump(self) -> dict[str, Any]:
        return self._data


async def _direct_completion(
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> _FakeResponse:
    if not api_base or not api_base.startswith(("http://", "https://")):
        raise _InvalidRequestError(
            f"Invalid base_url={api_base!r}. "
            "Configure it on the Settings page or in .env.",
        )
    if not api_key:
        raise _InvalidRequestError(
            "API key is empty. Set it on the Settings page or in .env.",
        )
    if not model:
        raise _InvalidRequestError(
            "Model is empty. Set it on the Settings page or in .env.",
        )

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{api_base.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        return _FakeResponse(r.json())


class SpendingLimitError(Exception):
    """Raised when the daily spending limit is exceeded."""


@dataclass
class _UsageRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    ts: datetime = field(default_factory=datetime.utcnow)


class SpendingTracker:
    """Thread-safe tracker for LLM usage and estimated costs."""

    def __init__(self) -> None:
        self._records: list[_UsageRecord] = []
        self._lock = asyncio.Lock()

    async def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        async with self._lock:
            self._records.append(
                _UsageRecord(
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost=0.0,
                )
            )
        logger.info(
            "llm_usage_tracked model={} prompt_tokens={} completion_tokens={} trace_id={}",
            model,
            prompt_tokens,
            completion_tokens,
            get_trace_id(),
        )

    async def get_daily_total(self) -> float:
        today = date.today()
        async with self._lock:
            return sum(r.cost for r in self._records if r.ts.date() == today)

    async def check_limit(self, limit_usd: float) -> None:
        total = await self.get_daily_total()
        if total > limit_usd:
            msg = f"Daily spending limit exceeded: ${total:.6f} > ${limit_usd:.6f}"
            raise SpendingLimitError(msg)


_spending_tracker = SpendingTracker()


def get_spending_tracker() -> SpendingTracker:
    """Return the module-level SpendingTracker instance."""
    return _spending_tracker


class AsyncLLMClient:
    """Async LLM client for any OpenAI-compatible endpoint."""

    def __init__(self) -> None:
        settings = get_settings()
        global_key = ""
        if settings.llm_api_key is not None:
            try:
                global_key = settings.llm_api_key.get_secret_value()
            except Exception:
                global_key = ""
        self.api_key = global_key
        self.daily_limit = settings.llm_daily_limit
        self.tracker = get_spending_tracker()

    async def acompletion(
        self,
        model_key: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_key_override: str | None = None,
        base_url_override: str | None = None,
    ) -> dict[str, Any]:
        """Call the LLM and return the raw response dict.

        Retries up to 3 times with exponential backoff (5s, 10s, 20s) for
        transient errors (5xx, network, 429 rate limits). Stops immediately
        on non-retryable statuses (401/403/404/422) and on structural
        errors raised by ``_direct_completion`` (empty URL / key / model).
        """
        await self.tracker.check_limit(self.daily_limit)

        api_key = api_key_override if api_key_override else self.api_key
        api_base = base_url_override if base_url_override else ""

        last_exception: Exception | None = None
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                response = await _direct_completion(
                    api_base=api_base,
                    api_key=api_key,
                    model=model_key,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except _InvalidRequestError as exc:
                # Structural — no point retrying. Bubble up as
                # MissingLLMConfigError so the pipeline surfaces a clean
                # message instead of three slow retries.
                logger.error(
                    "llm_invalid_request model={} error={} trace_id={}",
                    model_key,
                    str(exc)[:200],
                    get_trace_id(),
                )
                raise MissingLLMConfigError(str(exc)) from exc
            except Exception as exc:
                last_exception = exc
                status = _status_code_from_exception(exc)
                if status in NON_RETRYABLE_STATUSES:
                    logger.error(
                        "llm_non_retryable_status model={} status={} error={} trace_id={}",
                        model_key,
                        status,
                        str(exc)[:200],
                        get_trace_id(),
                    )
                    raise
                retry_delay = delay
                if hasattr(exc, "response") and hasattr(exc.response, "headers"):
                    retry_after = exc.response.headers.get("Retry-After", "")
                    if retry_after and retry_after.isdigit():
                        retry_delay = int(retry_after)
                logger.warning(
                    "llm_retry model={} attempt={}/{} delay={}s error={} trace_id={}",
                    model_key,
                    attempt + 1,
                    len(RETRY_DELAYS),
                    retry_delay,
                    str(exc)[:200],
                    get_trace_id(),
                )
                await asyncio.sleep(retry_delay)
                continue

            usage = getattr(response, "usage", None) or {}
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0

            await self.tracker.record_usage(
                model=model_key,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            return response.model_dump()

        msg = f"LLM call failed after {len(RETRY_DELAYS)} retries"
        raise RuntimeError(msg) from last_exception

    async def achat(
        self,
        model_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        api_key_override: str | None = None,
        base_url_override: str | None = None,
    ) -> str:
        """Convenience wrapper that returns the assistant's content string."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = await self.acompletion(
            model_key=model_key,
            messages=messages,
            temperature=temperature,
            api_key_override=api_key_override,
            base_url_override=base_url_override,
        )
        choices = response.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "") or ""


_client: AsyncLLMClient | None = None


def get_llm_client() -> AsyncLLMClient:
    """Return a singleton AsyncLLMClient instance."""
    global _client
    if _client is None:
        _client = AsyncLLMClient()
    return _client
