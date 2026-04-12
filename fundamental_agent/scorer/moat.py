# ============================================================
# scorer/moat.py — Moat & Efficiency Tier Scoring Engine
# ============================================================

import logging
from typing import Dict, Any

from fundamental_agent import config as cfg

logger = logging.getLogger(__name__)

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

def score_moat(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the Moat Tier scoring logic.
    Handles weight redistribution for Financial Services.
    """
    sector = data.get("sector", "Unknown")
    is_financial = sector == "Financial Services"

    metrics = {
        "gpm_score": 0.0,
        "opm_score": 0.0,
        "receivables_score": 0.0,
    }
    confidence_penalty = 0.0

    # Determine Active Weights (Redistribute if Financial Services)
    w_gpm = cfg.MOAT_WEIGHTS["gpm"]
    w_opm = cfg.MOAT_WEIGHTS["opm"]
    w_rec = cfg.MOAT_WEIGHTS["receivables_pct_sales"]

    if is_financial:
        # Banks don't have traditional receivables; their loan book IS their business.
        # Redistribute the 0.30 weight proportionally.
        total_margin_weight = w_gpm + w_opm
        w_gpm = w_gpm + (w_rec * (w_gpm / total_margin_weight))
        w_opm = w_opm + (w_rec * (w_opm / total_margin_weight))
        w_rec = 0.0

    # 1. Gross Profit Margin
    gpm = data.get("gpm")
    if gpm is not None:
        bounds = cfg.SCORING_BOUNDS["gpm"]
        metrics["gpm_score"] = _interpolate(gpm, bounds[0], bounds[1])
    else:
        metrics["gpm_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += w_gpm

    # 2. Operating Profit Margin
    opm = data.get("opm")
    if opm is not None:
        bounds = cfg.SCORING_BOUNDS["opm"]
        metrics["opm_score"] = _interpolate(opm, bounds[0], bounds[1])
    else:
        metrics["opm_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += w_opm

    # 3. Receivables % of Sales (Skipped for Financials)
    if not is_financial:
        rec = data.get("receivables_pct_sales")
        if rec is not None:
            bounds = cfg.SCORING_BOUNDS["receivables_pct_sales"]
            metrics["receivables_score"] = _interpolate(rec, bounds[0], bounds[1])
        else:
            metrics["receivables_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
            confidence_penalty += w_rec

    tier_score = (
        (metrics["gpm_score"] * w_gpm) +
        (metrics["opm_score"] * w_opm) +
        (metrics["receivables_score"] * w_rec)
    )

    confidence = 1.0 - confidence_penalty

    return {
        "tier_score": round(tier_score, 2),
        "confidence": round(confidence, 2),
        "is_financial_redistributed": is_financial,
        "metrics": metrics
    }