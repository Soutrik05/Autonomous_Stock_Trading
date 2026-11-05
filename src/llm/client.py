"""
LLMClient: one provider-agnostic `complete()` call per provider, each with its own HTTP
retry/backoff. Primary/fallback orchestration (the primary's own truncation/repair retries,
then one fallback attempt) lives in agents/parsers.py, not here, since it needs the parsed-
decision outcome to decide whether the primary "still failed". The model id for a given
provider instance is passed explicitly by the caller (agents/runner.py, from settings.LLM_MODEL
for the primary or settings.LLM_FALLBACK_MODEL for the fallback); each provider class falls
back to reading LLM_MODEL itself only when no model id is passed in. API keys are read from
GROQ_API_KEY/GEMINI_API_KEY and are never printed or logged. Logging each call to llm_calls
(with agent_id/run_date) is the caller's job (agents/runner.py).

Reasoning-model handling (openai/gpt-oss-120b on Groq, verified against the real API, see
docs/upstox_findings.md-style day-3c notes): `reasoning_effort` is only accepted by Groq's
OpenAI-compatible endpoint via `extra_body` -- the installed `groq` SDK (0.24.0) has no typed
kwarg for it. completion_tokens already includes any reasoning tokens; Groq additionally
reports them separately under usage.completion_tokens_details.reasoning_tokens. A truncated
reply has finish_reason == "length" (confirmed; content can even come back empty).

Gemini (`google-genai` SDK, verified against the real API): structured output must use
`response_json_schema` (raw JSON Schema), not `response_schema` (an OpenAPI-3.0 subset that
rejects our DecisionBatch schema's `additionalProperties: true` in Developer API mode).
`thinking_config.thinking_budget` controls reasoning (0 off, -1 dynamic, >0 a fixed token
budget); `usage_metadata.thoughts_token_count` reports it separately from candidates_token_count.
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
    provider: Optional[str] = None
    thinking_tokens: Optional[int] = None


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

    def __init__(self, responses: Optional[List] = None, model: str = "fake-model", provider: str = "fake"):
        self._responses = list(responses) if responses else []
        self.calls = []
        self._model = model
        self._provider = provider

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
            thinking_tokens = item.get("thinking_tokens")
        else:
            text, finish_reason, reasoning_tokens, thinking_tokens = item, "stop", None, None
        return LLMResult(
            text=text, tokens_in=len(system) + len(user), tokens_out=len(text), latency_ms=0,
            model=self._model, finish_reason=finish_reason, reasoning_tokens=reasoning_tokens,
            provider=self._provider, thinking_tokens=thinking_tokens,
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


def require_setting(value: str, name: str) -> str:
    """Raises a clear LLMConfigError naming `name` if a settings value (e.g. LLM_MODEL for the
    primary provider, LLM_FALLBACK_MODEL for the fallback) is missing. Needed because a provider
    class's own model requirement always checks LLM_MODEL regardless of which role it is being
    constructed for; the caller must check the role-specific setting itself."""
    if not value:
        raise LLMConfigError(f"{name} is not set; cannot construct an LLM provider.")
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
                provider="groq",
            )

        return _retry_with_backoff(_call, self._max_retries, self._backoff_base_sec, self._sleep)


_GEMINI_FINISH_REASON_MAP = {"STOP": "stop", "MAX_TOKENS": "length"}


class GeminiProvider(LLMClient):
    """Google's Gemini API via the official `google-genai` SDK (the new unified client, not the
    older `google.generativeai`). Structured output uses `response_json_schema` (accepts a raw
    JSON Schema, including $defs/discriminated unions/`additionalProperties: true`) rather than
    `response_schema` (an OpenAPI-3.0 subset that rejects `additionalProperties` in Developer API
    mode) -- confirmed empirically against the real API with our actual DecisionBatch schema."""

    def __init__(self, model: str = None, api_key: str = None, max_retries: int = 3,
                 backoff_base_sec: float = 1.0, sleep_func=time.sleep,
                 thinking_budget: Optional[int] = None):
        from google import genai
        from google.genai import errors as gerrors
        from google.genai import types as gtypes

        self._model_name = model or _require_env("LLM_MODEL")
        self._client = genai.Client(api_key=api_key or _require_env("GEMINI_API_KEY"))
        self._types = gtypes
        self._gerrors = gerrors
        self._thinking_budget = (
            thinking_budget if thinking_budget is not None else settings.LLM_GEMINI_THINKING_BUDGET
        )
        self._max_retries = max_retries
        self._backoff_base_sec = backoff_base_sec
        self._sleep = sleep_func

    def complete(self, system: str, user: str, reasoning_effort: Optional[str] = None,
                 max_output_tokens: Optional[int] = None, response_schema: Optional[dict] = None) -> LLMResult:
        types = self._types
        max_tokens = max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS
        config_kwargs = dict(
            system_instruction=system,
            temperature=settings.LLM_TEMPERATURE,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=self._thinking_budget),
        )
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_json_schema"] = response_schema
        config = types.GenerateContentConfig(**config_kwargs)

        def _call():
            start = time.monotonic()
            try:
                resp = self._client.models.generate_content(model=self._model_name, contents=user, config=config)
            except self._gerrors.ServerError as exc:
                raise _RetryableError(str(exc)) from exc
            except self._gerrors.ClientError as exc:
                if getattr(exc, "code", None) == 429:
                    raise _RetryableError(str(exc)) from exc
                raise
            latency_ms = int((time.monotonic() - start) * 1000)
            usage = resp.usage_metadata
            finish_reason = None
            if resp.candidates:
                raw = getattr(resp.candidates[0], "finish_reason", None)
                name = getattr(raw, "name", None) or getattr(raw, "value", None) or (str(raw) if raw else None)
                finish_reason = _GEMINI_FINISH_REASON_MAP.get(name, "other" if name else None)
            try:
                text = resp.text
            except Exception:
                text = ""
            return LLMResult(
                text=text or "",
                tokens_in=usage.prompt_token_count or 0,
                tokens_out=usage.candidates_token_count or 0,
                latency_ms=latency_ms,
                model=self._model_name,
                finish_reason=finish_reason,
                reasoning_tokens=None,
                provider="gemini",
                thinking_tokens=usage.thoughts_token_count,
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
