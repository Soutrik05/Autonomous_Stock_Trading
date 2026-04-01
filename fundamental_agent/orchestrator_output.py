# ============================================================
# orchestrator_output.py
# ============================================================
#
# Converts the raw output of run_fundamental_analysis() into a
# clean, orchestrator-ready JSON payload.
#
# Each entry in the output contains:
#   - ticker:    NSE symbol
#   - score:     0.0–1.0 float (raw 0–100 score divided by 100)
#   - reasoning: single string — positives + negatives + caveats
#
# Only stocks above ORCHESTRATOR_MIN_SCORE threshold are included.
# Disqualified and fetch-error stocks are excluded entirely.
#
# Output file: ORCHESTRATOR_OUTPUT_DIR/fundamental_YYYYMMDD_HHMMSS.json
#
# USAGE:
#   from orchestrator_output import build_and_save_orchestrator_payload
#   results = run_fundamental_analysis.invoke({"tickers": [...]})
#   path = build_and_save_orchestrator_payload(results)
# ============================================================

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from fundamental_agent import config as cfg


# ============================================================
# SECTION 1 — Reasoning String Builder
# ============================================================

def _build_reasoning(ticker: str, data: Dict[str, Any]) -> str:
    """
    Builds a single human-readable reasoning string from scored output.

    Structure:
        <VERDICT>. <Positives sentence>. <Negatives/caveats sentence>.

    Verdict is determined by score band:
        >= 0.75 → STRONG
        >= 0.60 → GOOD
        >= 0.50 → MODERATE
        (below threshold → not included in output)

    All inputs are derived from the already-computed flags and metric
    scores — no re-computation, no LLM call. Pure deterministic logic.
    """
    score      = data.get("score", 0) / 100.0
    sector     = data.get("sector") or "Unknown sector"
    scoring    = data.get("sector_scoring") or "universal"
    scores     = data.get("metric_scores") or {}
    flags      = data.get("flags") or []
    weights    = data.get("weights_used") or {}

    # ── Verdict ──────────────────────────────────────────────
    if score >= 0.75:
        verdict = "STRONG fundamental candidate"
    elif score >= 0.60:
        verdict = "GOOD fundamental candidate"
    else:
        verdict = "MODERATE fundamental candidate"

    # ── Collect positives ────────────────────────────────────
    # A metric is a positive if its score >= 70 (well above average).
    # Weight it proportionally — high-weight metrics mentioned first.
    METRIC_LABELS = {
        "roe":        "ROE",
        "eps_growth": "EPS growth",
        "pat_margin": "PAT margin",
        "de":         "debt level",
        "pe":         "PE valuation",
        "pb":         "PB valuation",
        "fcf":        "free cash flow",
    }

    positives = []
    negatives = []

    # Sort metrics by weight descending so most important leads
    sorted_metrics = sorted(
        scores.items(),
        key=lambda x: weights.get(x[0], 0),
        reverse=True
    )

    for metric, mscore in sorted_metrics:
        label = METRIC_LABELS.get(metric, metric)
        if mscore >= 70:
            positives.append(_describe_metric_positive(metric, mscore, data, scoring, sector))
        elif mscore <= 35 and mscore != cfg.SCORE_UNAVAILABLE_PENALTY:
            negatives.append(_describe_metric_negative(metric, mscore, data))
        elif mscore == cfg.SCORE_UNAVAILABLE_PENALTY:
            negatives.append(f"{label} data unavailable")

    # ── Extract warning flags ────────────────────────────────
    # Pull out flags that are genuine warnings (not just sector context)
    warning_flags = [
        f for f in flags
        if f.startswith("WARNING") or f.startswith("NOTE:")
    ]

    # ── Assemble reasoning ───────────────────────────────────
    parts = [f"{verdict} in {sector} sector ({scoring} benchmarks)."]

    if positives:
        parts.append("Positives: " + "; ".join(positives) + ".")
    else:
        parts.append("No strong standout positives — score driven by average metrics across the board.")

    if negatives:
        parts.append("Negatives: " + "; ".join(negatives) + ".")
    else:
        parts.append("No major fundamental negatives identified.")

    if warning_flags:
        parts.append("Caveats: " + " | ".join(warning_flags) + ".")

    # Sector scoring note — only when universal (less reliable)
    if scoring == "universal":
        parts.append(
            "Note: sector benchmarks unavailable — universal thresholds used, "
            "interpret relative scores with caution."
        )

    return " ".join(parts)


def _describe_metric_positive(
    metric: str,
    mscore: int,
    data: Dict[str, Any],
    scoring: str,
    sector: str,
) -> str:
    """Returns a short positive phrase for a well-scoring metric."""
    roe   = data.get("roe_pct")
    pat   = data.get("pat_margin_pct")
    eps_g = data.get("eps_growth_pct")
    de    = data.get("de")
    pe    = data.get("pe")
    pb    = data.get("pb")
    fcf   = data.get("fcf_crores")

    if metric == "roe" and roe is not None:
        ctx = f"vs sector median" if scoring == "relative" else "vs 15% universal threshold"
        return f"strong ROE of {roe:.1f}% ({ctx})"
    if metric == "eps_growth" and eps_g is not None:
        return f"solid EPS growth of {eps_g:.1f}% YoY"
    if metric == "pat_margin" and pat is not None:
        ctx = f"for {sector}" if scoring == "relative" else "above threshold"
        return f"healthy PAT margin of {pat:.1f}% ({ctx})"
    if metric == "de" and de is not None:
        return f"low leverage (D/E {de:.2f}x)"
    if metric == "pe" and pe is not None:
        return f"attractive valuation at PE {pe:.1f}x"
    if metric == "pb" and pb is not None:
        return f"reasonable PB of {pb:.1f}x"
    if metric == "fcf" and fcf is not None:
        return f"positive FCF of ₹{fcf:.0f} Cr"
    return f"{metric} score {mscore}"


def _describe_metric_negative(
    metric: str,
    mscore: int,
    data: Dict[str, Any],
) -> str:
    """Returns a short negative phrase for a poorly-scoring metric."""
    roe   = data.get("roe_pct")
    pat   = data.get("pat_margin_pct")
    eps_g = data.get("eps_growth_pct")
    de    = data.get("de")
    pe    = data.get("pe")
    pb    = data.get("pb")
    fcf   = data.get("fcf_crores")

    if metric == "roe" and roe is not None:
        return f"weak ROE of {roe:.1f}%"
    if metric == "eps_growth" and eps_g is not None:
        return f"declining EPS growth ({eps_g:.1f}% YoY)"
    if metric == "pat_margin" and pat is not None:
        return f"thin PAT margin of {pat:.1f}%"
    if metric == "de" and de is not None:
        return f"high leverage (D/E {de:.2f}x)"
    if metric == "pe" and pe is not None:
        return f"expensive valuation (PE {pe:.1f}x)"
    if metric == "pb" and pb is not None:
        return f"high PB of {pb:.1f}x"
    if metric == "fcf" and fcf is not None:
        sign = "negative" if fcf < 0 else "weak"
        return f"{sign} FCF (₹{fcf:.0f} Cr)"
    return f"{metric} score weak ({mscore})"


# ============================================================
# SECTION 2 — Payload Builder
# ============================================================

def build_orchestrator_payload(
    raw_results: Dict[str, Any],
    min_score: float = None,
) -> Dict[str, Any]:
    """
    Filters and formats the raw fundamental analysis output into the
    orchestrator-ready payload.

    Args:
        raw_results:  Output dict from run_fundamental_analysis().
        min_score:    Override the config threshold (0.0–1.0).
                      Defaults to cfg.ORCHESTRATOR_MIN_SCORE.

    Returns:
        Dict with keys:
            run_timestamp:  ISO format string
            threshold_used: float
            stocks_analysed: int
            stocks_passed:   int
            candidates:      list of {ticker, score, reasoning}
    """
    if min_score is None:
        min_score = cfg.ORCHESTRATOR_MIN_SCORE

    candidates = []

    for ticker, data in raw_results.items():
        # Skip errored and disqualified stocks entirely
        if data.get("fetch_error"):
            continue
        if data.get("disqualified"):
            continue

        raw_score = data.get("score", 0)
        normalised = round(raw_score / 100.0, 4)

        if normalised < min_score:
            continue

        reasoning = _build_reasoning(ticker, data)

        candidates.append({
            "ticker":    ticker,
            "score":     normalised,
            "reasoning": reasoning,
        })

    # Sort by score descending — orchestrator sees best candidates first
    candidates.sort(key=lambda x: x["score"], reverse=True)

    payload = {
        "run_timestamp":   datetime.now().isoformat(timespec="seconds"),
        "threshold_used":  min_score,
        "stocks_analysed": len(raw_results),
        "stocks_passed":   len(candidates),
        "candidates":      candidates,
    }

    return payload


# ============================================================
# SECTION 3 — Save to Timestamped JSON
# ============================================================

def save_payload(payload: Dict[str, Any], output_dir: str = None) -> str:
    """
    Saves the orchestrator payload to a timestamped JSON file.

    File naming: fundamental_YYYYMMDD_HHMMSS.json
    Creates the output directory if it doesn't exist.

    Returns the full path of the saved file.
    """
    if output_dir is None:
        output_dir = cfg.ORCHESTRATOR_OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    # Use timestamp from payload so filename matches run_timestamp exactly
    ts = payload["run_timestamp"].replace(":", "").replace("-", "").replace("T", "_")
    filename = f"fundamental_{ts}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return filepath


def build_and_save_orchestrator_payload(
    raw_results: Dict[str, Any],
    min_score: float = None,
    output_dir: str = None,
) -> str:
    """
    One-call convenience wrapper: build payload + save to disk.

    Returns the path of the saved JSON file.

    USAGE:
        results = run_fundamental_analysis.invoke({"tickers": tickers})
        path = build_and_save_orchestrator_payload(results)
        print(f"Saved to {path}")
    """
    payload  = build_orchestrator_payload(raw_results, min_score)
    filepath = save_payload(payload, output_dir)
    return filepath, payload
