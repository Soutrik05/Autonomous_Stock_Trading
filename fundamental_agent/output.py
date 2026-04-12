# ============================================================
# orchestrator_output.py
# ============================================================
import os
import csv
from datetime import datetime
from typing import Dict, Any

from fundamental_agent import config as cfg

# ============================================================
# SECTION 1 — Context-Aware Archetype Builder
# ============================================================

def _determine_archetype(tier_scores: Dict[str, float], raw_data: Dict[str, Any]) -> str:
    """
    Evaluates tier scores based strictly on Zerodha Varsity Module 3 investing principles.
    Focuses on Moats, Margin of Safety, and Consistent Wealth Creation.
    """
    q = tier_scores.get("quality", 0)
    g = tier_scores.get("growth", 0)
    v = tier_scores.get("valuation", 0)
    m = tier_scores.get("moat", 0)
    
    sector = raw_data.get("sector", "Unknown")
    is_financial = sector == "Financial Services" or sector == "Banking"

    # 1. Financial Specific (Varsity warns that Banks must be evaluated differently)
    if is_financial:
        if q >= 75 and g >= 70:
            return "High-Quality Financial Franchise"
        if q < 50:
            return "High-Risk Financial (NPA Threat)"

    # 2. The Varsity "Holy Grail" (Infosys/TCS/Page Ind examples from Module 3)
    if q >= 80 and m >= 80 and g >= 70:
        return "Consistent Wealth Creator (Strong Economic Moat)"

    # 3. The Graham/Buffett Ideal (Margin of Safety)
    if q >= 75 and v >= 75:
        return "Margin of Safety Play (High Quality + Undervalued)"

    # 4. Growth without Safety
    if q >= 70 and g >= 80 and v <= 40:
        return "High-Growth (Low Margin of Safety)"

    # 5. The Value Trap
    if q <= 45 and v >= 75:
        return "Value Trap (Cheap Valuation but Weak Fundamentals)"

    # 6. Wealth Destroyers (Avoid)
    if q <= 40 and m <= 40:
        return "Wealth Destroyer (Avoid - Weak Moat & Quality)"

    return "Average Performer (Requires Strict Checklist Review)"


def _get_contextual_callouts(tier_breakdown: Dict[str, Any], raw_data: Dict[str, Any]) -> str:
    """
    Finds the absolute strongest and absolute weakest specific metric 
    to add granular context to the archetype.
    """
    best_metric = ("", -1.0)
    worst_metric = ("", 101.0)
    
    for tier, t_data in tier_breakdown.items():
        if t_data.get("status") == "SKIPPED_LOW_CONFIDENCE":
            continue
            
        metrics = t_data.get("metrics", {})
        for m_key, m_score in metrics.items():
            if m_score == cfg.SCORE_UNAVAILABLE_PENALTY:
                continue
            if m_score > best_metric[1]:
                best_metric = (m_key, m_score)
            if m_score < worst_metric[1]:
                worst_metric = (m_key, m_score)

    callouts = []
    
    # Format Best Metric safely
    if best_metric[1] >= 80:
        k = best_metric[0]
        if k == "roe_or_roce_score":
            val = raw_data.get("roce") if raw_data.get("sector") in cfg.ASSET_HEAVY_SECTORS else raw_data.get("roe")
            if isinstance(val, (int, float)):
                callouts.append(f"exceptional capital efficiency ({val:.1f}%)")
        elif k == "pe_score":
            val = raw_data.get('pe_ratio')
            if isinstance(val, (int, float)):
                callouts.append(f"highly attractive PE ({val:.1f}x)")
        elif k == "profit_cagr_3yr_score":
            val = raw_data.get('profit_cagr_3yr')
            if isinstance(val, (int, float)):
                callouts.append(f"stellar profit growth ({val:.1f}%)")
        elif k == "gpm_score":
            callouts.append("massive gross margins")

    # Format Worst Metric safely
    if worst_metric[1] <= 30 and worst_metric[1] >= 0:
        k = worst_metric[0]
        if k == "pe_score":
            val = raw_data.get('pe_ratio')
            if isinstance(val, (int, float)):
                callouts.append(f"expensive valuation (PE {val:.1f}x)")
        elif k == "de_score":
            callouts.append("aggressive leverage")
        elif k == "revenue_cagr_3yr_score":
            callouts.append("stagnant topline growth")

    if callouts:
        return " | ".join(callouts)
    return ""


def _build_reasoning(ticker: str, score_report: Dict[str, Any], raw_data: Dict[str, Any]) -> str:
    """
    Builds the final reasoning string: 
    <VERDICT>. <ARCHETYPE>. <CONTEXT CALLOUTS>. <CAVEATS>.
    Now includes Alpha Signals (M-Score and Smart Money).
    """
    total_score = score_report.get("total_score", 0) / 100.0
    sector = raw_data.get("sector", "Unknown sector")
    breakdown = score_report.get("tier_breakdown", {})

    # 1. Verdict
    if total_score >= 0.75:
        verdict = f"STRONG candidate ({sector})"
    elif total_score >= 0.60:
        verdict = f"GOOD candidate ({sector})"
    elif total_score >= 0.40:
        verdict = f"MODERATE candidate ({sector})"
    else:
        verdict = f"POOR candidate ({sector})"

    # 2. Extract Tier Scores for Archetype mapping
    tier_scores = {
        tier: data.get("score", 0) 
        for tier, data in breakdown.items() 
        if data.get("status") != "SKIPPED_LOW_CONFIDENCE"
    }
    archetype = _determine_archetype(tier_scores, raw_data)
    
    # 3. Get granular fundamental callouts (best/worst feature)
    callout_str = _get_contextual_callouts(breakdown, raw_data)
    callouts = [callout_str] if callout_str else []


    # ── NEW: 4. Caveats & Red Flags Processing ──
    caveats = [
        f"Missing {t.capitalize()} data" for t, d in breakdown.items() 
        if d.get("status") == "SKIPPED_LOW_CONFIDENCE"
    ]
    
    m_score = raw_data.get("m_score_risk")
    if m_score == "HIGH":
        caveats.append("HIGH M-Score Risk (potential aggressive accounting)")
        
    if raw_data.get("pe_ratio") is None:
         caveats.append("PE ratio unavailable")

    # 5. Assemble Final String
    reasoning = f"{verdict}. Profile: {archetype}."
    
    if callouts:
        reasoning += f" Notable: {' | '.join(callouts)}."
        
    if caveats:
        reasoning += f" Caveat: {'; '.join(caveats)}."

    return reasoning

# ============================================================
# SECTION 2 — Payload Builder & CSV Saving
# ============================================================

def build_orchestrator_payload(raw_results: Dict[str, Any], min_score: float) -> Dict[str, Any]:

    candidates = []

    for ticker, bundle in raw_results.items():
        data = bundle["raw_data"]
        score_report = bundle["score_report"]
        
        raw_score = score_report.get("total_score", 0)
        normalised = round(raw_score / 100.0, 4)

        if normalised <= min_score:
            continue

        reasoning = _build_reasoning(ticker, score_report, data)

        candidates.append({
            "ticker":    ticker,
            "score":     normalised,
            "archetype": reasoning.split(".")[1].strip() if "." in reasoning else "Unknown",
            "reasoning": reasoning,
            "metrics":   data  # Kept here for CSV export
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    payload = {
        "run_timestamp":   datetime.now().isoformat(timespec="seconds"),
        "threshold_used":  min_score,
        "stocks_analysed": len(raw_results),
        "stocks_passed":   len(candidates),
        "candidates":      candidates,
    }

    return payload


def save_payload(payload: Dict[str, Any], output_dir: str = None) -> str:
    """Saves the full payload to a timestamped CSV file for high readability."""
    if output_dir is None:
        output_dir = cfg.ORCHESTRATOR_OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)
    ts = payload["run_timestamp"].replace(":", "").replace("-", "").replace("T", "_")
    filename = f"fundamental_{ts}.csv"
    filepath = os.path.join(output_dir, filename)

    candidates = payload.get("candidates", [])
    
    if not candidates:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write("ticker,score,reasoning\n")
        return filepath

    base_headers = ["ticker", "score", "reasoning"]
    metric_keys = list(candidates[0].get("metrics", {}).keys())
    if "ticker" in metric_keys:
        metric_keys.remove("ticker")
        
    all_headers = base_headers + metric_keys

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["# RUN METADATA"])
        writer.writerow(["# Timestamp", payload["run_timestamp"]])
        writer.writerow(["# Threshold", payload["threshold_used"]])
        writer.writerow(["# Analysed", payload["stocks_analysed"]])
        writer.writerow(["# Passed", payload["stocks_passed"]])
        writer.writerow([])
        writer.writerow(all_headers)
        
        for c in candidates:
            row = [c.get("ticker", ""), c.get("score", ""), c.get("reasoning", "")]
            metrics = c.get("metrics", {})
            for m_key in metric_keys:
                row.append(metrics.get(m_key, ""))
            writer.writerow(row)

    return filepath