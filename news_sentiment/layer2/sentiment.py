# layer2/sentiment.py

import torch
import pandas as pd
from transformers import pipeline
from news_sentiment.layer2.config import BATCH_SIZE
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline


def load_finbert():
    device = 0 if torch.cuda.is_available() else -1
    print(f"[FinBERT] Loading (device: {'GPU' if device == 0 else 'CPU'})...")

    model_name = "ProsusAI/finbert"

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            use_safetensors=False
        )

        finbert = pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            device=device,
            top_k=None
        )

        print("[FinBERT] Loaded ProsusAI/finbert ✅")

    except Exception as e:
        print(f"[FinBERT] Primary model failed: {e}")
        print("[FinBERT] Falling back to finbert-tone...")

        finbert = pipeline(
            "text-classification",
            model="yiyanghkust/finbert-tone",
            device=device
        )

        print("[FinBERT] Loaded fallback model ✅")

    return finbert


def score_text(finbert, text: str) -> dict:
    empty = {"label": "neutral", "score": 0.0, "positive_prob": 0.0,
             "negative_prob": 0.0, "neutral_prob": 1.0, "confidence": 0.0}

    if not isinstance(text, str) or not text.strip():
        return empty

    try:
        probs  = {r["label"]: r["score"] for r in finbert(text[:2048])[0]}
        pos, neg, neu = probs.get("positive", 0.0), probs.get("negative", 0.0), probs.get("neutral", 0.0)
        return {
            "label":         max(probs, key=probs.get),
            "score":         round(pos - neg, 4),
            "positive_prob": round(pos, 4),
            "negative_prob": round(neg, 4),
            "neutral_prob":  round(neu, 4),
            "confidence":    round(max(pos, neg, neu), 4)
        }
    except Exception as e:
        print(f"[FinBERT] Error: {e}")
        return empty


def _build_scoring_text(row) -> str:
    title   = str(row["title"]).strip()   if pd.notna(row["title"])   else ""
    summary = str(row["summary"]).strip() if pd.notna(row["summary"]) else ""
    return title if not summary else f"{title}. {title}. {summary}"


def score_dataframe(finbert, df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["scoring_text"] = df.apply(_build_scoring_text, axis=1)
    print(f"[FinBERT] Scoring {len(df)} articles...")

    results = []
    for i in range(0, len(df), BATCH_SIZE):
        for text in df["scoring_text"].iloc[i:i + BATCH_SIZE].tolist():
            results.append(score_text(finbert, text))
        if (i // BATCH_SIZE) % 5 == 0:
            print(f"  {min(i + BATCH_SIZE, len(df))}/{len(df)}...")

    print("[FinBERT] Done.")
    return pd.concat([df.drop(columns=["scoring_text"]), pd.DataFrame(results)], axis=1)