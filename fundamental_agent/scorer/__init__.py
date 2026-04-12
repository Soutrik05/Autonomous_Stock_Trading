# ============================================================
# scorer.py — Master Scoring Orchestrator
# ============================================================

import logging
from typing import Dict, Any

from fundamental_agent import config as cfg
from fundamental_agent.scorer.growth import score_growth
from fundamental_agent.scorer.quality import score_quality
from fundamental_agent.scorer.valuation import score_valuation
from fundamental_agent.scorer.moat import score_moat

logger = logging.getLogger(__name__)

def calculate_total_score(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrates the four scoring tiers, applies weights, handles 
    confidence thresholds, and calculates the final Fundamental Score.
    """
    ticker = data.get("ticker", "UNKNOWN")
    logger.info(f"[{ticker}] Calculating Master Fundamental Score...")

    # 1. Run Individual Tiers
    growth_results = score_growth(data)
    quality_results = score_quality(data)
    val_results = score_valuation(data)
    moat_results = score_moat(data)

    tiers = {
        "growth": {"results": growth_results, "weight": cfg.TIER_WEIGHTS["growth"]},
        "quality": {"results": quality_results, "weight": cfg.TIER_WEIGHTS["quality"]},
        "valuation": {"results": val_results, "weight": cfg.TIER_WEIGHTS["valuation"]},
        "moat": {"results": moat_results, "weight": cfg.TIER_WEIGHTS["moat"]},
    }

    total_score = 0.0
    active_weight_sum = 0.0
    tier_breakdown = {}

    # 2. Process Tiers & Check Confidence
    for tier_name, tier_data in tiers.items():
        results = tier_data["results"]
        weight = tier_data["weight"]
        confidence = results["confidence"]

        # If we are missing too much data for this tier, we drop it.
        if confidence < cfg.TIER_CONFIDENCE_THRESHOLD:
            logger.warning(
                f"[{ticker}] Dropping {tier_name.upper()} tier due to low confidence "
                f"({confidence:.2f} < {cfg.TIER_CONFIDENCE_THRESHOLD})."
            )
            tier_breakdown[tier_name] = {
                "score": 0.0,
                "status": "SKIPPED_LOW_CONFIDENCE",
                "metrics": results.get("metrics", {})
            }
            continue

        # Tier passed confidence check; add to total
        total_score += (results["tier_score"] * weight)
        active_weight_sum += weight
        
        tier_breakdown[tier_name] = {
            "score": results["tier_score"],
            "status": "ACTIVE",
            "metrics": results.get("metrics", {})
        }

    # 3. Mathematical Re-normalization
    # If a tier was dropped, the active weights won't sum to 1.0. 
    # We must re-normalize the score so it is still graded out of 100%.
    if active_weight_sum > 0:
        final_normalized_score = total_score / active_weight_sum
    else:
        # Extreme Edge Case: Screener and YFinance completely failed.
        logger.error(f"[{ticker}] ALL tiers failed confidence checks. Score is 0.")
        final_normalized_score = 0.0

    logger.info(f"[{ticker}] Final Score: {final_normalized_score:.2f}/100 "
                f"(Based on {active_weight_sum*100:.0f}% of total weights).")
    

    # 4. Alpha Signal Overlays (Master Modifiers)
    
    # A. 5-Factor Accrual & Manipulation Check (Scaled Penalty)
    m_comps = data.get("m_score_components", {})
    data["m_score_risk"] = "LOW" # Default for Orchestrator

    if data.get("sector") != "Financial Services" and m_comps:
        flags = 0
        red_flags = []
        
        # Manipulation Thresholds
        if m_comps.get("dsri") and m_comps["dsri"] > 1.2:
            flags += 1; red_flags.append("DSRI")
        if m_comps.get("gmi") and m_comps["gmi"] > 1.15:
            flags += 1; red_flags.append("GMI")
        if m_comps.get("sgi") and m_comps["sgi"] > 1.25:
            flags += 1; red_flags.append("SGI")
        if m_comps.get("lvgi") and m_comps["lvgi"] > 1.05:
            flags += 1; red_flags.append("LVGI")
        if m_comps.get("tata") and m_comps["tata"] > 0.05: # Accruals > 5% of Assets
            flags += 1; red_flags.append("TATA")
            
        if flags >= 3:
            logger.warning(f"[{ticker}] CRITICAL M-Score Risk! {flags} flags ({','.join(red_flags)}). -20 pts.")
            final_normalized_score -= 20.0
            data["m_score_risk"] = "HIGH"
        elif flags == 2:
            logger.warning(f"[{ticker}] Moderate M-Score Risk. {flags} flags ({','.join(red_flags)}). -10 pts.")
            final_normalized_score -= 10.0
            data["m_score_risk"] = "MODERATE"
        elif flags == 1:
            logger.info(f"[{ticker}] Minor accounting anomaly ({red_flags[0]}). -5 pts.")
            final_normalized_score -= 5.0

    # B. NEW: Mega-Cap Premium (Size & Stability)
    # A market cap over ₹1 Lakh Crore indicates immense stability.
    # We award a 10-point baseline bump to offset the CapEx penalties massive companies incur.
    mcap_cr = data.get("market_cap_crores")
    if mcap_cr is not None:
        if mcap_cr > 100000: # Greater than 1 Lakh Crore
            logger.info(f"[{ticker}] Mega-Cap Premium: Adding +10 points for extreme scale and stability.")
            final_normalized_score += 10.0
        elif mcap_cr > 50000: # Greater than 50k Crore
            logger.info(f"[{ticker}] Large-Cap Premium: Adding +5 points for scale.")
            final_normalized_score += 5.0

    # Ensure the final score strictly stays within the 0 to 100 bounds
    final_normalized_score = max(0.0, min(100.0, final_normalized_score))

    logger.info(f"[{ticker}] Final Score: {final_normalized_score:.2f}/100 "
                f"(Based on {active_weight_sum*100:.0f}% of total weights).")

    return {
        "ticker": ticker,
        "total_score": round(final_normalized_score, 2),
        "active_weights_used": round(active_weight_sum, 2),
        "tier_breakdown": tier_breakdown
    }