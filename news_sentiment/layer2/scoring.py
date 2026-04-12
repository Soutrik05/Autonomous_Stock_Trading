# layer2/scoring.py
# Produces the final output this agent is responsible for:
# weighted_score + signal_strength per stock per date → handed off to orchestrator

import pandas as pd
from news_sentiment.layer2.config import SOURCE_WEIGHTS, SCORE_THRESHOLDS, CONFIDENCE_MIN


def apply_weights(scored_df: pd.DataFrame) -> pd.DataFrame:
    df = scored_df.copy()
    df["source_weight"] = df["source"].map(SOURCE_WEIGHTS).fillna(0.60)

    counts = (
        df.groupby("title")["matched_symbol"].count()
        .reset_index().rename(columns={"matched_symbol": "companies_mentioned"})
    )
    df = df.merge(counts, on="title", how="left")

    def specificity(row):
        title = str(row["title"]).lower()
        n     = row["companies_mentioned"]
        list_patterns = [
            "stocks to buy", "stocks to watch", "top stocks", "these stocks",
            "stocks gain", "stocks fall", "multibagger", "largecap", "midcap"
        ]
        if any(p in title for p in list_patterns): return 1.0
        if n == 1:  return 1.0
        if n == 2:  return 0.75
        return 1 / n

    df["specificity_weight"] = df.apply(specificity, axis=1)
    df["combined_weight"]    = df["source_weight"] * df["specificity_weight"] * df["confidence"]
    return df


def _parse_date(val):
    if pd.isna(val): return pd.NaT
    try:    return pd.to_datetime(val, utc=True).normalize().tz_localize(None)
    except Exception:
        try:    return pd.to_datetime(val).normalize()
        except: return pd.NaT


def aggregate_per_stock(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = df["published"].apply(_parse_date)

    def agg(group):
        w  = group["combined_weight"]
        s  = group["score"]
        tw = w.sum()
        lc = group["label"].value_counts()
        return pd.Series({
            "weighted_score":    round((s * w).sum() / tw if tw > 0 else 0.0, 4),
            "dominant_label":    lc.idxmax(),
            "article_count":     len(group),
            "positive_count":    lc.get("positive", 0),
            "negative_count":    lc.get("negative", 0),
            "neutral_count":     lc.get("neutral",  0),
            "avg_confidence":    round(group["confidence"].mean(), 4),
            "bse_announcement":  int((group["source"] == "BSE Announcement").any()),
            "specific_articles": int((group["companies_mentioned"] <= 2).sum()),
            "sources":           ", ".join(group["source"].unique()),
        })

    print("[Scoring] Aggregating per stock per date...")
    daily_df = (
        df.dropna(subset=["date"])
        .groupby(["matched_symbol", "matched_company", "matched_industry", "date"])
        .apply(agg)
        .reset_index()
        .sort_values(["date", "weighted_score"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return daily_df


def add_signal_strength(daily_df: pd.DataFrame) -> pd.DataFrame:
    def signal(row):
        s, c = row["weighted_score"], row["avg_confidence"]
        if c < CONFIDENCE_MIN:                           return "WEAK"
        if s >= SCORE_THRESHOLDS["STRONG_POSITIVE"]:    return "STRONG POSITIVE"
        if s >= SCORE_THRESHOLDS["POSITIVE"]:           return "POSITIVE"
        if s <= SCORE_THRESHOLDS["STRONG_NEGATIVE"]:    return "STRONG NEGATIVE"
        if s <= SCORE_THRESHOLDS["NEGATIVE"]:           return "NEGATIVE"
        return "NEUTRAL"

    daily_df = daily_df.copy()
    daily_df["signal_strength"] = daily_df.apply(signal, axis=1)
    return daily_df


def build_layer2_output(scored_df: pd.DataFrame) -> pd.DataFrame:
    """
    Full Layer 2 pipeline.
    Input : FinBERT-scored master_df
    Output: daily_df with weighted_score + signal_strength per stock
            → save to Excel and/or pass to orchestrator
    """
    weighted_df = apply_weights(scored_df)
    daily_df    = aggregate_per_stock(weighted_df)
    daily_df    = add_signal_strength(daily_df)

    print(f"\n[Layer2] {len(daily_df)} (stock, date) pairs")
    print(daily_df["signal_strength"].value_counts().to_string())
    return daily_df


# ── Orchestrator handoff ───────────────────────────────────────────────────────
# This is what you pass to the orchestrator agent.
# They receive a list of dicts with these fields only.

def get_orchestrator_payload(daily_df: pd.DataFrame) -> list[dict]:
    """
    Returns a clean list of dicts — one per (stock, date).
    The orchestrator uses weighted_score + signal_strength to make decisions.
    """
    cols = [
        "matched_symbol", "matched_company", "matched_industry", "date",
        "weighted_score", "signal_strength", "avg_confidence",
        "bse_announcement", "article_count", "sources"
    ]
    return daily_df[cols].to_dict(orient="records")