"""
LLMClient: provider abstraction, retries, and a fallback to a second provider. The model id is
read from the LLM_MODEL environment variable with no default (raises if unset); API keys are
read from GROQ_API_KEY/GEMINI_API_KEY and are never printed or logged. Logging each call to
llm_calls (with agent_id/run_date) is the caller's job (agents/runner.py), since providers here
have no notion of which agent or run date is calling them.
See Plan_v3 §3.2.
"""
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str


class LLMClient(ABC):
    """Provider-agnostic interface for one system+user prompt, text-out LLM call."""

    @abstractmethod
    def complete(self, system: str, user: str) -> LLMResult:
        raise NotImplementedError


class FakeLLMClient(LLMClient):
    """Returns a scripted sequence of responses for tests and replay; makes no network calls."""

    def __init__(self, responses: Optional[List[str]] = None, model: str = "fake-model"):
        self._responses = list(responses) if responses else []
        self.calls = []
        self._model = model

    def complete(self, system: str, user: str) -> LLMResult:
        self.calls.append({"system": system, "user": user})
        text = self._responses.pop(0) if self._responses else '{"decisions": []}'
        return LLMResult(
            text=text,
            tokens_in=len(system) + len(user),
            tokens_out=len(text),
            latency_ms=0,
            model=self._model,
        )


class LLMConfigError(RuntimeError):
    """A required environment variable (LLM_MODEL, an API key) is missing."""


class _RetryableError(Exception):
    """Internal marker: the underlying provider call failed with a retryable (429/5xx) status."""


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise LLMConfigError(f"{name} is not set in the environment; cannot construct an LLM provider.")
    return value


def _retry_with_backoff(call_fn, max_retries: int, backoff_base_sec: float, sleep_func):
    attempt = 0
    while True:
        try:
            return call_fn()
        except _RetryableError:
            if attempt >= max_retries:
                raise
            sleep_func(backoff_base_sec * (2 ** attempt))
            attempt += 1


class GroqProvider(LLMClient):
    """Groq's chat completions API via the official `groq` SDK."""

    def __init__(self, model: str = None, api_key: str = None, max_retries: int = 3,
                 backoff_base_sec: float = 1.0, sleep_func=time.sleep):
        import groq

        self._model = model or _require_env("LLM_MODEL")
        self._client = groq.Groq(api_key=api_key or _require_env("GROQ_API_KEY"))
        self._groq = groq
        self._max_retries = max_retries
        self._backoff_base_sec = backoff_base_sec
        self._sleep = sleep_func

    def complete(self, system: str, user: str) -> LLMResult:
        def _call():
            start = time.monotonic()
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
            except self._groq.APIStatusError as exc:
                if getattr(exc, "status_code", None) in RETRYABLE_HTTP_CODES:
                    raise _RetryableError(str(exc)) from exc
                raise
            latency_ms = int((time.monotonic() - start) * 1000)
            return LLMResult(
                text=resp.choices[0].message.content,
                tokens_in=resp.usage.prompt_tokens,
                tokens_out=resp.usage.completion_tokens,
                latency_ms=latency_ms,
                model=resp.model,
            )

        return _retry_with_backoff(_call, self._max_retries, self._backoff_base_sec, self._sleep)


class GeminiProvider(LLMClient):
    """Google's Gemini API via the official `google-generativeai` SDK."""

    def __init__(self, model: str = None, api_key: str = None, max_retries: int = 3,
                 backoff_base_sec: float = 1.0, sleep_func=time.sleep):
        import google.generativeai as genai
        from google.api_core import exceptions as gexc

        self._model_name = model or _require_env("LLM_MODEL")
        genai.configure(api_key=api_key or _require_env("GEMINI_API_KEY"))
        self._genai = genai
        self._retryable_exc = (gexc.ResourceExhausted, gexc.ServiceUnavailable,
                                gexc.InternalServerError, gexc.DeadlineExceeded)
        self._max_retries = max_retries
        self._backoff_base_sec = backoff_base_sec
        self._sleep = sleep_func

    def complete(self, system: str, user: str) -> LLMResult:
        def _call():
            start = time.monotonic()
            model = self._genai.GenerativeModel(self._model_name, system_instruction=system)
            try:
                resp = model.generate_content(user)
            except self._retryable_exc as exc:
                raise _RetryableError(str(exc)) from exc
            latency_ms = int((time.monotonic() - start) * 1000)
            usage = resp.usage_metadata
            return LLMResult(
                text=resp.text,
                tokens_in=usage.prompt_token_count,
                tokens_out=usage.candidates_token_count,
                latency_ms=latency_ms,
                model=self._model_name,
            )

        return _retry_with_backoff(_call, self._max_retries, self._backoff_base_sec, self._sleep)


_PROVIDERS = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
}


def build_provider(name: str, **kwargs) -> LLMClient:
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        raise LLMConfigError(f"Unknown LLM provider {name!r}; expected one of {sorted(_PROVIDERS)}") from None
    return provider_cls(**kwargs)


class FallbackLLMClient(LLMClient):
    """Tries `primary`; if it raises, tries `fallback`. Raises the fallback's exception (chained
    to the primary's) if both fail."""

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self._primary = primary
        self._fallback = fallback

    def complete(self, system: str, user: str) -> LLMResult:
        try:
            return self._primary.complete(system, user)
        except Exception as primary_exc:
            try:
                return self._fallback.complete(system, user)
            except Exception as fallback_exc:
                raise fallback_exc from primary_exc
