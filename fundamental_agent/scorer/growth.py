# ============================================================
# scorer/growth.py — Growth Tier Scoring Engine
# ============================================================

import logging
from typing import Dict, Any

from fundamental_agent import config as cfg

logger = logging.getLogger(__name__)

def _interpolate(value: float, worst: float, best: float) -> float:
    """Linearly interpolates a score between 0 and 100."""
    if value is None:
        return 0.0
    if worst < best: # Higher is better
        if value <= worst: return 0.0
        if value >= best: return 100.0
        return ((value - worst) / (best - worst)) * 100.0
    else: # Lower is better
        if value >= worst: return 0.0
        if value <= best: return 100.0
        return ((worst - value) / (worst - best)) * 100.0

def score_growth(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the Growth Tier scoring logic using continuous interpolation.
    """
    metrics = {
        "revenue_cagr_3yr_score": 0.0,
        "profit_cagr_3yr_score": 0.0,
        "eps_growth_1yr_score": 0.0,
    }
    
    confidence_penalty = 0.0

    # 1. Revenue CAGR Scoring
    rev_cagr = data.get("revenue_cagr_3yr")
    if rev_cagr is not None:
        bounds = cfg.SCORING_BOUNDS["revenue_cagr_3yr"]
        metrics["revenue_cagr_3yr_score"] = _interpolate(rev_cagr, bounds[0], bounds[1])
    else:
        metrics["revenue_cagr_3yr_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += cfg.GROWTH_WEIGHTS["revenue_cagr_3yr"]

    # 2. Profit CAGR Scoring
    prof_cagr = data.get("profit_cagr_3yr")
    if prof_cagr is not None:
        bounds = cfg.SCORING_BOUNDS["profit_cagr_3yr"]
        metrics["profit_cagr_3yr_score"] = _interpolate(prof_cagr, bounds[0], bounds[1])
    else:
        metrics["profit_cagr_3yr_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += cfg.GROWTH_WEIGHTS["profit_cagr_3yr"]

    # 3. EPS Growth (1 Year) Scoring
    eps_growth = data.get("eps_growth_1yr")
    if eps_growth is not None:
        bounds = cfg.SCORING_BOUNDS["eps_growth_1yr"]
        metrics["eps_growth_1yr_score"] = _interpolate(eps_growth, bounds[0], bounds[1])
    else:
        metrics["eps_growth_1yr_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += cfg.GROWTH_WEIGHTS["eps_growth_1yr"]

    # Calculate Weighted Tier Score
    tier_score = (
        (metrics["revenue_cagr_3yr_score"] * cfg.GROWTH_WEIGHTS["revenue_cagr_3yr"]) +
        (metrics["profit_cagr_3yr_score"]  * cfg.GROWTH_WEIGHTS["profit_cagr_3yr"]) +
        (metrics["eps_growth_1yr_score"]   * cfg.GROWTH_WEIGHTS["eps_growth_1yr"])
    )

    confidence = 1.0 - confidence_penalty

    return {
        "tier_score": round(tier_score, 2),
        "confidence": round(confidence, 2),
        "metrics": metrics
    }