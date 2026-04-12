# ============================================================
# scorer/quality.py — Quality Tier Scoring Engine
# ============================================================

import logging
from typing import Dict, Any, Tuple

from fundamental_agent import config as cfg

logger = logging.getLogger(__name__)

def _calculate_z_score(value: float, median: float, range_low: float, range_high: float) -> float:
    """
    Calculates a pseudo Z-Score based on sector benchmarks.
    Returns a normalized score between 0 and 100.
    """
    if value is None:
        return 0.0
        
    spread = range_high - range_low
    if spread <= 0:
        spread = 1.0 # Prevent division by zero
        
    # Assume half the spread represents roughly 1 "standard deviation"
    std_dev = spread / 2.0
    
    # How many standard deviations is the value from the median?
    z = (value - median) / std_dev
    
    # Base score is 50 (at the median). Each std_dev adds/subtracts 25 points.
    raw_score = 50.0 + (z * 25.0)
    
    return max(0.0, min(100.0, raw_score))

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

def _score_debt_to_equity(de: float, roce: float, is_asset_heavy: bool, sector: str) -> float:
    """
    Calculates the D/E score using the Leverage Efficiency Modifier.
    """
    if de is None:
        return cfg.SCORE_UNAVAILABLE_PENALTY

    # Banks and NBFCs literally sell debt. Traditional D/E doesn't apply.
    if sector == "Financial Services":
        return _interpolate(de, worst=12.0, best=4.0)

    # Standard bounds for Asset Light
    worst_de = 3.0
    best_de = 0.0

    # Leverage Efficiency Modifier for Asset Heavy
    if is_asset_heavy and roce is not None:
        if roce >= cfg.LEVERAGE_EFFICIENCY_BASELINE_ROCE:
            # Productive Leverage: The company is generating great returns on debt.
            # We widen the "worst" bound, effectively softening the penalty.
            efficiency_ratio = roce / cfg.LEVERAGE_EFFICIENCY_BASELINE_ROCE
            worst_de = worst_de * efficiency_ratio
        else:
            # Destructive Leverage: High debt, low returns. Keep bounds strict.
            pass

    return _interpolate(de, worst=worst_de, best=best_de)

def score_quality(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the Quality Tier scoring logic.
    """
    sector = data.get("sector", "Unknown")
    is_asset_heavy = sector in cfg.ASSET_HEAVY_SECTORS
    
    # Get sector benchmarks (fallback to a generic benchmark if unknown)
    benchmarks = cfg.SECTOR_BENCHMARKS.get(sector, {
        "roe_median": 15, "roe_range": (10, 20),
        "pat_median": 10, "pat_range": (5, 15)
    })

    metrics = {
        "roe_or_roce_score": 0.0,
        "pat_margin_score": 0.0,
        "fcf_score": 0.0,
        "de_score": 0.0,
    }
    
    confidence_penalty = 0.0

    # 1. ROE / ROCE Scoring (Z-Score)
    primary_return_metric = data.get("roce") if is_asset_heavy else data.get("roe")
    fallback_metric = data.get("roe") if is_asset_heavy else data.get("roce")
    
    active_metric = primary_return_metric if primary_return_metric is not None else fallback_metric
    
    if active_metric is not None:
        metrics["roe_or_roce_score"] = _calculate_z_score(
            active_metric, 
            benchmarks["roe_median"], 
            benchmarks["roe_range"][0], 
            benchmarks["roe_range"][1]
        )
    else:
        metrics["roe_or_roce_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += cfg.QUALITY_WEIGHTS["roe_or_roce"]

    # 2. PAT Margin Scoring (Z-Score)
    pat = data.get("pat_margin")
    if pat is not None:
        metrics["pat_margin_score"] = _calculate_z_score(
            pat, 
            benchmarks["pat_median"], 
            benchmarks["pat_range"][0], 
            benchmarks["pat_range"][1]
        )
    else:
        metrics["pat_margin_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += cfg.QUALITY_WEIGHTS["pat_margin"]

    # 3. Free Cash Flow Scoring (Continuous Interpolation)
    fcf = data.get("fcf_crores")
    if fcf is not None:
        bounds = cfg.SCORING_BOUNDS["fcf_crores"]
        metrics["fcf_score"] = _interpolate(fcf, bounds[0], bounds[1])
    else:
        metrics["fcf_score"] = cfg.SCORE_UNAVAILABLE_PENALTY
        confidence_penalty += cfg.QUALITY_WEIGHTS["fcf"]

    # 4. Debt to Equity Scoring (Leverage Efficiency)
    metrics["de_score"] = _score_debt_to_equity(
        data.get("debt_to_equity"), 
        active_metric, # Pass ROCE/ROE to judge leverage efficiency
        is_asset_heavy, 
        sector
    )
    if data.get("debt_to_equity") is None:
        confidence_penalty += cfg.QUALITY_WEIGHTS["de"]

    # Calculate Weighted Tier Score
    tier_score = (
        (metrics["roe_or_roce_score"] * cfg.QUALITY_WEIGHTS["roe_or_roce"]) +
        (metrics["pat_margin_score"]  * cfg.QUALITY_WEIGHTS["pat_margin"]) +
        (metrics["fcf_score"]         * cfg.QUALITY_WEIGHTS["fcf"]) +
        (metrics["de_score"]          * cfg.QUALITY_WEIGHTS["de"])
    )

    # Calculate data availability confidence
    confidence = 1.0 - confidence_penalty

    return {
        "tier_score": round(tier_score, 2),
        "confidence": round(confidence, 2),
        "is_asset_heavy": is_asset_heavy,
        "metrics": metrics
    }