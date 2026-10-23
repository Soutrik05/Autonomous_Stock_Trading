"""
Unit tests for llm/client.py's GroqProvider and GeminiProvider against faked SDK objects (no
network). Covers day 5a: Gemini's thinking_budget reaching the real request config, structured
output, finish-reason mapping, empty-text/MAX_TOKENS treated as a failed attempt, a 429 that
retries then succeeds, and a clear error when an API key or model id is missing.
See Plan_v3 §3.2.
"""
from types import SimpleNamespace

import pytest

from agents.parsers import is_truncated
from llm.client import GeminiProvider, GroqProvider, LLMConfigError, build_provider, require_setting


# --- GeminiProvider: faked google-genai SDK ---------------------------------------------------


class _FakeGeminiUsage:
    def __init__(self, prompt_tokens=10, candidates_tokens=5, thoughts_tokens=None):
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = candidates_tokens
        self.thoughts_token_count = thoughts_tokens


class _FakeGeminiResponse:
    def __init__(self, text, finish_reason_name="STOP", thoughts_tokens=None):
        self.text = text
        self.candidates = [SimpleNamespace(finish_reason=SimpleNamespace(name=finish_reason_name))]
        self.usage_metadata = _FakeGeminiUsage(thoughts_tokens=thoughts_tokens)


class _FakeGeminiModels:
    """Records every generate_content call; replays a scripted sequence of responses/exceptions."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.captured_configs = []

    def generate_content(self, model, contents, config):
        self.captured_configs.append(config)
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeGeminiClient:
    def __init__(self, scripted):
        self.models = _FakeGeminiModels(scripted)


def _make_gemini_provider(monkeypatch, scripted, **kwargs):
    from google import genai

    client = _FakeGeminiClient(scripted)
    monkeypatch.setattr(genai, "Client", lambda api_key: client)
    provider = GeminiProvider(model="gemini-flash-latest", api_key="fake-key", sleep_func=lambda s: None, **kwargs)
    return provider, client


def test_gemini_thinking_budget_reaches_the_request_for_0_1024_and_dynamic(monkeypatch):
    for budget in (0, 1024, -1):
        provider, client = _make_gemini_provider(
            monkeypatch, [_FakeGeminiResponse('{"decisions": []}')], thinking_budget=budget,
        )
        provider.complete("system", "user", response_schema={"type": "object"})
        config = client.models.captured_configs[0]
        assert config.thinking_config.thinking_budget == budget


def test_gemini_structured_output_uses_response_json_schema_not_response_schema(monkeypatch):
    schema = {"type": "object", "properties": {"decisions": {"type": "array"}}}
    provider, client = _make_gemini_provider(monkeypatch, [_FakeGeminiResponse('{"decisions": []}')])
    provider.complete("system", "user", response_schema=schema)
    config = client.models.captured_configs[0]
    assert config.response_json_schema == schema
    assert config.response_schema is None
    assert config.response_mime_type == "application/json"


def test_gemini_finish_reason_stop_maps_to_stop(monkeypatch):
    provider, _ = _make_gemini_provider(monkeypatch, [_FakeGeminiResponse("hello", finish_reason_name="STOP")])
    result = provider.complete("system", "user")
    assert result.finish_reason == "stop"
    assert result.provider == "gemini"


def test_gemini_finish_reason_max_tokens_maps_to_length_and_is_truncated(monkeypatch):
    provider, _ = _make_gemini_provider(
        monkeypatch, [_FakeGeminiResponse("cut off", finish_reason_name="MAX_TOKENS")],
    )
    result = provider.complete("system", "user")
    assert result.finish_reason == "length"
    assert is_truncated(result) is True  # a MAX_TOKENS finish is treated as a failed attempt


def test_gemini_empty_text_counts_as_a_failed_attempt(monkeypatch):
    provider, _ = _make_gemini_provider(monkeypatch, [_FakeGeminiResponse("", finish_reason_name="STOP")])
    result = provider.complete("system", "user")
    assert is_truncated(result) is True


def test_gemini_other_finish_reason_maps_to_other(monkeypatch):
    provider, _ = _make_gemini_provider(monkeypatch, [_FakeGeminiResponse("x", finish_reason_name="SAFETY")])
    result = provider.complete("system", "user")
    assert result.finish_reason == "other"


def test_gemini_thinking_tokens_are_reported_separately_from_candidates_tokens(monkeypatch):
    provider, _ = _make_gemini_provider(
        monkeypatch, [_FakeGeminiResponse("hi", thoughts_tokens=42)],
    )
    result = provider.complete("system", "user")
    assert result.thinking_tokens == 42
    assert result.tokens_out == 5  # candidates_token_count, unaffected by thinking tokens


def test_gemini_429_retries_then_succeeds(monkeypatch):
    from google.genai import errors as gerrors

    rate_limited = gerrors.ClientError(429, {"error": {"message": "rate limited"}})
    provider, client = _make_gemini_provider(monkeypatch, [rate_limited, _FakeGeminiResponse("ok")])
    result = provider.complete("system", "user")
    assert result.text == "ok"
    assert len(client.models.captured_configs) == 2  # one retryable failure, one success


def test_gemini_non_retryable_client_error_raises_immediately(monkeypatch):
    from google.genai import errors as gerrors

    not_found = gerrors.ClientError(404, {"error": {"message": "model not found"}})
    provider, _ = _make_gemini_provider(monkeypatch, [not_found])
    with pytest.raises(gerrors.ClientError):
        provider.complete("system", "user")


def test_gemini_missing_api_key_gives_a_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="GEMINI_API_KEY"):
        GeminiProvider(model="gemini-flash-latest")


def test_missing_model_id_gives_a_clear_error_naming_the_right_setting():
    with pytest.raises(LLMConfigError, match="LLM_FALLBACK_MODEL"):
        require_setting("", "LLM_FALLBACK_MODEL")


def test_unknown_provider_name_gives_a_clear_error():
    with pytest.raises(LLMConfigError, match="unknown_llm"):
        build_provider("unknown_llm")


# --- GroqProvider: faked groq SDK -------------------------------------------------------------


class _FakeGroqUsage:
    def __init__(self, prompt_tokens=10, completion_tokens=5, reasoning_tokens=None):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.completion_tokens_details = SimpleNamespace(reasoning_tokens=reasoning_tokens)


class _FakeGroqResponse:
    def __init__(self, text, finish_reason="stop", model="openai/gpt-oss-120b", reasoning_tokens=None):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish_reason)]
        self.usage = _FakeGroqUsage(reasoning_tokens=reasoning_tokens)
        self.model = model


class _FakeGroqCompletions:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _make_groq_provider(monkeypatch, scripted):
    import groq

    completions = _FakeGroqCompletions(scripted)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(groq, "Groq", lambda api_key: fake_client)
    provider = GroqProvider(model="openai/gpt-oss-120b", api_key="fake-key", sleep_func=lambda s: None)
    return provider, completions


def test_groq_429_retries_then_succeeds(monkeypatch):
    import httpx
    import groq

    http_response = httpx.Response(status_code=429, request=httpx.Request("POST", "https://fake"))
    rate_limited = groq.APIStatusError("rate limited", response=http_response, body=None)
    provider, completions = _make_groq_provider(monkeypatch, [rate_limited, _FakeGroqResponse("ok")])
    result = provider.complete("system", "user")
    assert result.text == "ok"
    assert result.provider == "groq"
    assert len(completions.calls) == 2


def test_groq_missing_api_key_gives_a_clear_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="GROQ_API_KEY"):
        GroqProvider(model="openai/gpt-oss-120b")
