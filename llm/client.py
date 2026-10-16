"""
LLMClient: provider abstraction, retries, inter-agent call spacing, and logging to llm_calls.
Only the abstract interface and a FakeLLMClient for tests are defined here; real providers
(Groq, Gemini, OpenRouter) are added in a later task.
See Plan_v3 §3.2.
"""
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Provider-agnostic interface for one prompt-in, text-out LLM call."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Sends `prompt` to the model and returns the raw text response."""
        raise NotImplementedError


class FakeLLMClient(LLMClient):
    """Returns a pre-set response (or sequence of responses) for tests and replay, no network calls."""

    def __init__(self, responses=None):
        self._responses = list(responses) if responses else []
        self.calls = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return '{"decisions": []}'
