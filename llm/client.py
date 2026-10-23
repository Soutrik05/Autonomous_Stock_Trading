"""
LLMClient: provider abstraction, retries, and a fallback to a second provider. The model id is
read from the LLM_MODEL environment variable with no default (raises if unset); API keys are
read from GROQ_API_KEY/GEMINI_API_KEY and are never printed or logged. Logging each call to
llm_calls (with agent_id/run_date) is the caller's job (agents/runner.py).

Reasoning-model handling (openai/gpt-oss-120b on Groq, verified against the real API, see
docs/upstox_findings.md-style day-3c notes): `reasoning_effort` is only accepted by Groq's
OpenAI-compatible endpoint via `extra_body` -- the installed `groq` SDK (0.24.0) has no typed
kwarg for it. completion_tokens already includes any reasoning tokens; Groq additionally
reports them separately under usage.completion_tokens_details.reasoning_tokens. A truncated
reply has finish_reason == "length" (confirmed; content can even come back empty).
See Plan_v3 §3.2.
"""
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from settings import settings

RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}

# Groq's own low->high ordering for GPT-OSS models (the only tiers that model supports).
_REASONING_EFFORT_TIERS = ["low", "medium", "high"]


def step_down_reasoning_effort(effort: str) -> str:
    """One tier lower than `effort` (low/medium/high); "low" has no lower tier and is returned
    unchanged -- the retry then relies on the raised max_output_tokens instead."""
    try:
        idx = _REASONING_EFFORT_TIERS.index(effort)
    except ValueError:
        return "low"
    return _REASONING_EFFORT_TIERS[max(idx - 1, 0)]


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str
    finish_reason: Optional[str] = None
    reasoning_tokens: Optional[int] = None


class LLMClient(ABC):
    """Provider-agnostic interface for one system+user prompt, text-out LLM call."""

    @abstractmethod
    def complete(
        self, system: str, user: str, reasoning_effort: Optional[str] = None,
        max_output_tokens: Optional[int] = None, response_schema: Optional[dict] = None,
    ) -> LLMResult:
        raise NotImplementedError


class FakeLLMClient(LLMClient):
    """Returns a scripted sequence of responses for tests and replay; makes no network calls.
    Each scripted response is either a plain string (finish_reason='stop') or a dict
    {"text", "finish_reason", "reasoning_tokens"} for simulating truncation etc."""

    def __init__(self, responses: Optional[List] = None, model: str = "fake-model"):
        self._responses = list(responses) if responses else []
        self.calls = []
        self._model = model

    def complete(self, system: str, user: str, reasoning_effort: Optional[str] = None,
                 max_output_tokens: Optional[int] = None, response_schema: Optional[dict] = None) -> LLMResult:
        self.calls.append({
            "system": system, "user": user, "reasoning_effort": reasoning_effort,
            "max_output_tokens": max_output_tokens,
        })
        item = self._responses.pop(0) if self._responses else '{"decisions": []}'
        if isinstance(item, dict):
            text = item.get("text", "")
            finish_reason = item.get("finish_reason", "stop")
            reasoning_tokens = item.get("reasoning_tokens")
        else:
            text, finish_reason, reasoning_tokens = item, "stop", None
        return LLMResult(
            text=text, tokens_in=len(system) + len(user), tokens_out=len(text), latency_ms=0,
            model=self._model, finish_reason=finish_reason, reasoning_tokens=reasoning_tokens,
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
    """Groq's chat completions API via the official `groq` SDK. `reasoning_effort` is passed
    through `extra_body` (confirmed necessary against the installed SDK version)."""

    def __init__(self, model: str = None, api_key: str = None, max_retries: int = 3,
                 backoff_base_sec: float = 1.0, sleep_func=time.sleep):
        import groq

        self._model = model or _require_env("LLM_MODEL")
        self._client = groq.Groq(api_key=api_key or _require_env("GROQ_API_KEY"))
        self._groq = groq
        self._max_retries = max_retries
        self._backoff_base_sec = backoff_base_sec
        self._sleep = sleep_func

    def complete(self, system: str, user: str, reasoning_effort: Optional[str] = None,
                 max_output_tokens: Optional[int] = None, response_schema: Optional[dict] = None) -> LLMResult:
        effort = reasoning_effort or settings.LLM_REASONING_EFFORT
        max_tokens = max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS

        kwargs = dict(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=settings.LLM_TEMPERATURE,
            max_completion_tokens=max_tokens,
            extra_body={"reasoning_effort": effort},
        )
        if response_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "decision_batch", "strict": False, "schema": response_schema},
            }

        def _call():
            start = time.monotonic()
            try:
                resp = self._client.chat.completions.create(**kwargs)
            except self._groq.APIStatusError as exc:
                if getattr(exc, "status_code", None) in RETRYABLE_HTTP_CODES:
                    raise _RetryableError(str(exc)) from exc
                raise
            latency_ms = int((time.monotonic() - start) * 1000)
            usage = resp.usage
            details = getattr(usage, "completion_tokens_details", None)
            reasoning_tokens = getattr(details, "reasoning_tokens", None) if details else None
            return LLMResult(
                text=resp.choices[0].message.content or "",
                tokens_in=usage.prompt_tokens,
                tokens_out=usage.completion_tokens,
                latency_ms=latency_ms,
                model=resp.model,
                finish_reason=resp.choices[0].finish_reason,
                reasoning_tokens=reasoning_tokens,
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

    def complete(self, system: str, user: str, reasoning_effort: Optional[str] = None,
                 max_output_tokens: Optional[int] = None, response_schema: Optional[dict] = None) -> LLMResult:
        max_tokens = max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS
        generation_config = {"temperature": settings.LLM_TEMPERATURE, "max_output_tokens": max_tokens}
        if response_schema is not None:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_schema

        def _call():
            start = time.monotonic()
            model = self._genai.GenerativeModel(self._model_name, system_instruction=system)
            try:
                resp = model.generate_content(user, generation_config=generation_config)
            except self._retryable_exc as exc:
                raise _RetryableError(str(exc)) from exc
            latency_ms = int((time.monotonic() - start) * 1000)
            usage = resp.usage_metadata
            finish_reason = None
            if resp.candidates:
                raw = getattr(resp.candidates[0], "finish_reason", None)
                name = getattr(raw, "name", str(raw)) if raw is not None else None
                finish_reason = {"STOP": "stop", "MAX_TOKENS": "length"}.get(name, (name or "").lower() or None)
            try:
                text = resp.text
            except Exception:
                text = ""
            return LLMResult(
                text=text or "",
                tokens_in=usage.prompt_token_count,
                tokens_out=usage.candidates_token_count,
                latency_ms=latency_ms,
                model=self._model_name,
                finish_reason=finish_reason,
                reasoning_tokens=None,
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

    def complete(self, system: str, user: str, reasoning_effort: Optional[str] = None,
                 max_output_tokens: Optional[int] = None, response_schema: Optional[dict] = None) -> LLMResult:
        try:
            return self._primary.complete(system, user, reasoning_effort, max_output_tokens, response_schema)
        except Exception as primary_exc:
            try:
                return self._fallback.complete(system, user, reasoning_effort, max_output_tokens, response_schema)
            except Exception as fallback_exc:
                raise fallback_exc from primary_exc
