# ============================================================
# scorer/valuation.py — Valuation Tier Scoring Engine
# ============================================================

import logging
from typing import Dict, Any

from fundamental_agent import config as cfg

logger = logging.getLogger(__name__)

def _calculate_inverted_z_score(value: float, median: float, range_low: float, range_high: float) -> float:
    """
    Calculates an inverted Z-Score (Lower values = Higher Score).
    Used specifically for relative valuation metrics like P/E.
    """
    if value is None or value <= 0:
        return 0.0 # Negative P/E (loss-making) gets zero points for valuation
        
    spread = range_high - range_low
    if spread <= 0: spread = 1.0
        
    std_dev = spread / 2.0
    
    # Inverted logic: If value is LESS than median, z is positive
    z = (median - value) / std_dev
    
    raw_score = 50.0 + (z * 25.0)
    return max(0.0, min(100.0, raw_score))

def _interpolate(value: float, worst: float, best: float) -> float:
    """Linearly interpolates a score between 0 and 100."""
    if value is None: return 0.0
    if worst < best:
        if value <= worst: return 0.0
        if value >= best: return 100.0
        return ((value - worst) / (best - worst)) * 100.0
    else: # Lower is better
        if value >= worst: return 0.0
        if value <= best: return 100.0
        return ((worst - value) / (worst - best)) * 100.0

def score_valuation(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the Valuation Tier scoring logic.
    """

    ticker = data.get("ticker", "UNKNOWN")
    pe = data.get("pe_ratio")
    pb = data.get("pb_ratio")

    # ── THE NEGATIVE EARNINGS TRAP FIX ──
    # If PE or PB is negative, the company is generating losses or has negative equity.
    if (pe is not None and pe < 0) or (pb is not None and pb < 0):
        logger.warning(f"[{ticker}] Negative PE/PB detected. Generating losses. Valuation score = 0.")
        return {
            "tier_score": 0.0,
            "confidence": 1.0, # We are 100% confident this deserves a zero
            "metrics": {
                "pe_score": 0.0,
                "pb_score": 0.0
            }
        }

    sector = data.get("sector", "Unknown")
    benchmarks = cfg.SECTOR_BENCHMARKS.get(sector, {
        "pe_median": 20, "pe_range": (15, 30)
    })

    metrics = {
        "pe_score": 0.0,
        "pb_score": 0.0,
    }
    confidence_penalty = 0.0

    # 1. P/E Ratio vs Sector (Inverted Z-Score)
    if pe is not None:
        metrics["pe_score"] = _calculate_inverted_z_score(
            pe, 
            benchmarks["pe_median"], 
            benchmarks["pe_range"][0], 
            benchmarks["pe_range"][1]
        )
    else:
        metrics["pe_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += cfg.VALUATION_WEIGHTS["pe_vs_sector"]

    # 2. P/B Ratio (Continuous Interpolation)
    if pb is not None:
        bounds = cfg.SCORING_BOUNDS["pb"]
        metrics["pb_score"] = _interpolate(pb, bounds[0], bounds[1])
    else:
        metrics["pb_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += cfg.VALUATION_WEIGHTS["pb"]

    tier_score = (
        (metrics["pe_score"] * cfg.VALUATION_WEIGHTS["pe_vs_sector"]) +
        (metrics["pb_score"] * cfg.VALUATION_WEIGHTS["pb"])
    )

    confidence = 1.0 - confidence_penalty

    return {
        "tier_score": round(tier_score, 2),
        "confidence": round(confidence, 2),
        "metrics": metrics
    }