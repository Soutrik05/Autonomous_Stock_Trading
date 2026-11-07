"""
FinBERT Sentiment Analyzer.
Loads ProsusAI/finbert pipeline locally to score financial headlines and summaries.
Produces positive_prob, negative_prob, neutral_prob, confidence, and sentiment_score in [-1.0, 1.0].
"""

from typing import Any

_SCORER_INSTANCE = None


class FinBertScorer:
    def __init__(self, model_name: str = "ProsusAI/finbert", device: int | None = None):
        self.model_name = model_name
        self._pipeline = None
        self._device = device

    def _ensure_loaded(self):
        if self._pipeline is not None:
            return

        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

        if self._device is None:
            self._device = 0 if torch.cuda.is_available() else -1

        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self._pipeline = pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            device=self._device,
            top_k=None,
        )

    def score_text(self, text: str) -> dict[str, Any]:
        """Scores a single text string."""
        batch_res = self.score_batch([text])
        return batch_res[0] if batch_res else self._empty_result()

    def score_batch(self, texts: list[str], batch_size: int = 32) -> list[dict[str, Any]]:
        """Scores a batch of text strings."""
        if not texts:
            return []

        self._ensure_loaded()
        results: list[dict[str, Any]] = []

        # Clean and truncate texts to ~512 characters/tokens
        cleaned = [t.strip()[:1024] if isinstance(t, str) and t.strip() else "" for t in texts]

        for i in range(0, len(cleaned), batch_size):
            chunk = cleaned[i : i + batch_size]
            valid_indices = [idx for idx, t in enumerate(chunk) if t]
            valid_texts = [chunk[idx] for idx in valid_indices]

            chunk_results = [self._empty_result() for _ in chunk]

            if valid_texts:
                pipe_outputs = self._pipeline(valid_texts)
                for sub_idx, output in enumerate(pipe_outputs):
                    orig_idx = valid_indices[sub_idx]
                    probs = {item["label"].lower(): item["score"] for item in output}
                    pos = probs.get("positive", 0.0)
                    neg = probs.get("negative", 0.0)
                    neu = probs.get("neutral", 0.0)
                    sentiment_score = round(pos - neg, 4)
                    confidence = round(max(pos, neg, neu), 4)

                    if pos > neg and pos > neu:
                        label = "positive"
                    elif neg > pos and neg > neu:
                        label = "negative"
                    else:
                        label = "neutral"

                    chunk_results[orig_idx] = {
                        "sentiment_score": sentiment_score,
                        "positive_prob": round(pos, 4),
                        "negative_prob": round(neg, 4),
                        "neutral_prob": round(neu, 4),
                        "confidence": confidence,
                        "label": label,
                    }

            results.extend(chunk_results)

        return results

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "sentiment_score": 0.0,
            "positive_prob": 0.0,
            "negative_prob": 0.0,
            "neutral_prob": 1.0,
            "confidence": 1.0,
            "label": "neutral",
        }


def get_finbert_scorer() -> FinBertScorer:
    """Returns singleton FinBertScorer instance."""
    global _SCORER_INSTANCE
    if _SCORER_INSTANCE is None:
        _SCORER_INSTANCE = FinBertScorer()
    return _SCORER_INSTANCE


def set_finbert_scorer(scorer: FinBertScorer | None):
    """Sets or resets the global FinBertScorer (used in tests for mocking)."""
    global _SCORER_INSTANCE
    _SCORER_INSTANCE = scorer
