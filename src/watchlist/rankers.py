"""
Stage 2 Cross-Sectional Strategy Rankers and Stage 0 Heuristic Scorers.

Decomposes the Stage 2 intensity ranking responsibility from watchlist/watchlist_refresh.py
into cohesive, testable, per-persona ranking functions adhering to AQR/factor model standards.

Each ranker receives:
    - stage1_tickers: list of tickers that survived Stage 1 hurdles
    - features_by_ticker: mapping of ticker to feature snapshot dict
    - sector_by_ticker: mapping of ticker to sector string
    - sector_percentiles: optional mapping of ticker to within-sector percentile (0-100)

And returns:
    List[dict] sorted by descending intensity_score:
    [
        {
            "ticker": str,
            "sector": str,
            "intensity_score": float,
            "raw_score": float,
            "sector_percentile": float,
        },
        ...
    ]
"""
from typing import Callable, Dict, List, Optional
import pandas as pd


# =================================================================================================
# Stage 0 / Fallback Single-Stock Heuristic Scoring Functions
# Used for Stage 0 sector cohort percentile ranking and standalone score evaluation.
# =================================================================================================

def score_simons(features: dict) -> float:
    """Conviction metric for Jimmy: KER * (ADX / 25) * min(volume_surge, 3.0)."""
    ker = features.get("kaufman_er_20") or 0.0
    adx = features.get("adx_14") or 0.0
    volume_surge = features.get("volume_surge") or 1.0
    obv_slope = features.get("obv_slope_sign") or 0
    penalty = 0.8 if obv_slope < 0 else 1.0
    return round(ker * (adx / 25.0) * min(volume_surge, 3.0) * penalty, 4)


def score_lynch(features: dict) -> float:
    """Multi-factor GARP standalone heuristic score."""
    roce = features.get("roce_pct")
    if roce is None:
        return float("-inf")
    peg = features.get("peg")
    cfo = features.get("cfo_to_pat")
    peg_val = max(0.01, float(peg)) if peg is not None and peg > 0 else 1.0
    cfo_val = max(0.1, float(cfo)) if cfo is not None else 1.0
    pat_growth = float(features.get("pat_growth_yoy_pct") or 0.0)
    bonus = 1.10 if pat_growth >= 15.0 else 1.0
    return round((float(roce) / peg_val) * min(2.0, cfo_val) * bonus, 4)


def score_marks(features: dict) -> float:
    """Contrarian quality-oversold standalone heuristic score."""
    rsi = features.get("rsi_14")
    if rsi is None:
        return float("-inf")
    dist_52w = float(features.get("dist_52w_low_pct") or 10.0)
    oversold = (100.0 - float(rsi)) * (1.0 / max(1.0, dist_52w))
    roce = float(features.get("roce_pct") or 10.0)
    cfo = max(0.1, float(features.get("cfo_to_pat") or 1.0))
    de = max(0.1, float(features.get("debt_to_equity") or 0.5))
    quality = (roce * cfo) / de
    regime = str(features.get("regime") or "").upper()
    panic_mult = 1.25 if regime == "PANIC" else (1.10 if regime == "ELEVATED" else 1.0)
    return round(oversold * quality * panic_mult, 4)


def score_rj(features: dict) -> float:
    """Growth compounder standalone heuristic score."""
    volume_surge = features.get("volume_surge")
    if volume_surge is None:
        return float("-inf")
    pat_growth = float(features.get("pat_growth_yoy_pct") or 10.0)
    roce = float(features.get("roce_pct") or 15.0)
    inst_delta = float(features.get("fii_dii_qoq_delta_pct") or 0.0)
    promoter = float(features.get("promoter_holding_pct") or 40.0)
    promoter_bonus = 1.10 if promoter >= 50.0 else 1.0
    inst_mult = 1.0 + max(-0.2, min(0.3, inst_delta / 10.0))
    return round(float(volume_surge) * (pat_growth / 10.0) * (roce / 15.0) * inst_mult * promoter_bonus, 4)


def score_varsity(features: dict) -> float:
    """Balanced technical and fundamental confluence standalone score."""
    rsi = features.get("rsi_14")
    if rsi is None:
        return float("-inf")
    volume_surge = float(features.get("volume_surge") or 1.0)
    roce = float(features.get("roce_pct") or 12.0)
    roe = float(features.get("roe_pct") or 12.0)
    de = max(0.1, float(features.get("debt_to_equity") or 0.8))
    sentiment = float(features.get("news_sentiment") or 0.0)
    sentiment_mult = 1.10 if sentiment > 0.10 else 1.0
    dcf = features.get("dcf_discount_pct")
    dcf_mult = 1.0 + max(-0.2, min(0.3, (dcf / 100.0))) if dcf is not None else 1.0
    return round((float(rsi) / 50.0) * (roce / 12.0) * (roe / 12.0) * (1.0 / de) * min(2.5, volume_surge) * dcf_mult * sentiment_mult, 4)


# Dictionary mapping persona sort keys to their heuristic scoring functions
SORT_KEYS: Dict[str, Callable[[dict], float]] = {
    "simons_intensity": score_simons,
    "lynch_intensity": score_lynch,
    "marks_intensity": score_marks,
    "rj_intensity": score_rj,
    "varsity_intensity": score_varsity,
}


# =================================================================================================
# Stage 2 Cross-Sectional Percentile Rankers
# =================================================================================================

def _format_scored_candidates(
    stage1_tickers: List[str],
    scores: Dict[str, float],
    sector_by_ticker: Dict[str, str],
    sector_percentiles: Optional[Dict[str, float]] = None,
) -> List[dict]:
    """Helper to format and sort candidate dictionary list by descending intensity."""
    scored = []
    for t in stage1_tickers:
        raw_score = scores[t]
        sector = sector_by_ticker.get(t, "UNKNOWN")
        pct = (sector_percentiles or {}).get(t, 50.0)
        scored.append({
            "ticker": t,
            "sector": sector,
            "intensity_score": raw_score,
            "raw_score": raw_score,
            "sector_percentile": round(pct, 2),
        })
    scored.sort(key=lambda row: row["intensity_score"], reverse=True)
    return scored


def rank_simons_intensity(
    stage1_tickers: List[str],
    features_by_ticker: Dict[str, dict],
    sector_by_ticker: Dict[str, str],
    sector_percentiles: Optional[Dict[str, float]] = None,
) -> List[dict]:
    """
    Cross-Sectional Percentile Rank Composite for Jim Simons (AQR Factor Model Standard).
    - Factor 1: Volume Conviction (volume_surge)
    - Factor 2: Trend Efficiency (kaufman_er_20)
    - Factor 3: Directional Trend Strength (adx_14)
    - Directional consistency penalty: 20% discount if obv_slope_sign == -1
    """
    if not stage1_tickers:
        return []

    vol_vals = [float(features_by_ticker[t].get("volume_surge") or 1.0) for t in stage1_tickers]
    ker_vals = [float(features_by_ticker[t].get("kaufman_er_20") or 0.0) for t in stage1_tickers]
    adx_vals = [float(features_by_ticker[t].get("adx_14") or 0.0) for t in stage1_tickers]

    vol_ranks = pd.Series(vol_vals, index=stage1_tickers).rank(pct=True).to_dict()
    ker_ranks = pd.Series(ker_vals, index=stage1_tickers).rank(pct=True).to_dict()
    adx_ranks = pd.Series(adx_vals, index=stage1_tickers).rank(pct=True).to_dict()

    scores = {}
    for t in stage1_tickers:
        feat = features_by_ticker[t]
        obv_slope = feat.get("obv_slope_sign") or 0
        penalty = 0.8 if obv_slope < 0 else 1.0
        composite = ((vol_ranks[t] + ker_ranks[t] + adx_ranks[t]) / 3.0) * penalty
        scores[t] = round(composite, 4)

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_lynch_intensity(
    stage1_tickers: List[str],
    features_by_ticker: Dict[str, dict],
    sector_by_ticker: Dict[str, str],
    sector_percentiles: Optional[Dict[str, float]] = None,
) -> List[dict]:
    """
    Cross-Sectional Multi-Factor GARP Percentile Composite for Peter Lynch.
    - Factor 1: Valuation Edge (lower PEG is better -> rank inverse of peg)
    - Factor 2: Capital Productivity (higher ROCE is better)
    - Factor 3: Cash Conversion Quality (higher CFO/PAT is better)
    - Growth acceleration kicker: 10% bonus if pat_growth_yoy_pct >= 15.0%
    """
    if not stage1_tickers:
        return []

    inv_peg_vals = [1.0 / max(0.01, float(features_by_ticker[t].get("peg") or 1.0)) for t in stage1_tickers]
    roce_vals = [float(features_by_ticker[t].get("roce_pct") or 15.0) for t in stage1_tickers]
    cfo_vals = [float(features_by_ticker[t].get("cfo_to_pat") or 0.8) for t in stage1_tickers]

    peg_ranks = pd.Series(inv_peg_vals, index=stage1_tickers).rank(pct=True).to_dict()
    roce_ranks = pd.Series(roce_vals, index=stage1_tickers).rank(pct=True).to_dict()
    cfo_ranks = pd.Series(cfo_vals, index=stage1_tickers).rank(pct=True).to_dict()

    scores = {}
    for t in stage1_tickers:
        pat_growth = float(features_by_ticker[t].get("pat_growth_yoy_pct") or 0.0)
        bonus = 1.10 if pat_growth >= 15.0 else 1.0
        composite = (peg_ranks[t] + roce_ranks[t] + cfo_ranks[t]) / 3.0
        scores[t] = min(1.0, round(composite * bonus, 4))

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_marks_intensity(
    stage1_tickers: List[str],
    features_by_ticker: Dict[str, dict],
    sector_by_ticker: Dict[str, str],
    sector_percentiles: Optional[Dict[str, float]] = None,
) -> List[dict]:
    """
    Cross-Sectional Contrarian Quality-Oversold Percentile Composite for Howard Marks.
    - Factor 1: Oversold Velocity (lower RSI is better -> rank (100 - RSI))
    - Factor 2: Proximity to 52-Week Low (lower dist_52w_low_pct is better -> rank -dist_52w_low_pct)
    - Factor 3: Quality & Balance Sheet Solvency (ROCE * CFO/PAT / D/E)
    - Macro panic multiplier: PANIC -> 1.25x, ELEVATED -> 1.10x, NORMAL/LOW_VOL -> 1.0x
    """
    if not stage1_tickers:
        return []

    rsi_inv = [100.0 - float(features_by_ticker[t].get("rsi_14") or 50.0) for t in stage1_tickers]
    dist_inv = [-float(features_by_ticker[t].get("dist_52w_low_pct") or 20.0) for t in stage1_tickers]
    qual_vals = [
        (float(features_by_ticker[t].get("roce_pct") or 10.0) * max(0.1, float(features_by_ticker[t].get("cfo_to_pat") or 1.0)))
        / max(0.1, float(features_by_ticker[t].get("debt_to_equity") or 0.5))
        for t in stage1_tickers
    ]

    rsi_ranks = pd.Series(rsi_inv, index=stage1_tickers).rank(pct=True).to_dict()
    dist_ranks = pd.Series(dist_inv, index=stage1_tickers).rank(pct=True).to_dict()
    qual_ranks = pd.Series(qual_vals, index=stage1_tickers).rank(pct=True).to_dict()

    scores = {}
    for t in stage1_tickers:
        oversold_rank = 0.5 * rsi_ranks[t] + 0.5 * dist_ranks[t]
        regime = str(features_by_ticker[t].get("regime") or "").upper()
        panic_mult = 1.25 if regime == "PANIC" else (1.10 if regime == "ELEVATED" else 1.0)
        composite = ((oversold_rank + qual_ranks[t]) / 2.0) * panic_mult
        scores[t] = min(1.0, round(composite, 4))

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_rj_intensity(
    stage1_tickers: List[str],
    features_by_ticker: Dict[str, dict],
    sector_by_ticker: Dict[str, str],
    sector_percentiles: Optional[Dict[str, float]] = None,
) -> List[dict]:
    """
    Cross-Sectional Growth Compounder Percentile Composite for Rakesh Jhunjhunwala.
    - Factor 1: Earnings Growth Velocity (pat_growth_yoy_pct)
    - Factor 2: Institutional Footprint / Accumulation (fii_dii_qoq_delta_pct)
    - Factor 3: Breakout Volume Conviction (volume_surge)
    - Factor 4: Capital Return Efficiency (roce_pct)
    - Promoter skin-in-the-game bonus: 10% if promoter_holding_pct >= 50%
    """
    if not stage1_tickers:
        return []

    growth_vals = [float(features_by_ticker[t].get("pat_growth_yoy_pct") or 0.0) for t in stage1_tickers]
    inst_vals = [float(features_by_ticker[t].get("fii_dii_qoq_delta_pct") or 0.0) for t in stage1_tickers]
    vol_vals = [float(features_by_ticker[t].get("volume_surge") or 1.0) for t in stage1_tickers]
    roce_vals = [float(features_by_ticker[t].get("roce_pct") or 15.0) for t in stage1_tickers]

    growth_ranks = pd.Series(growth_vals, index=stage1_tickers).rank(pct=True).to_dict()
    inst_ranks = pd.Series(inst_vals, index=stage1_tickers).rank(pct=True).to_dict()
    vol_ranks = pd.Series(vol_vals, index=stage1_tickers).rank(pct=True).to_dict()
    roce_ranks = pd.Series(roce_vals, index=stage1_tickers).rank(pct=True).to_dict()

    scores = {}
    for t in stage1_tickers:
        promoter = float(features_by_ticker[t].get("promoter_holding_pct") or 0.0)
        bonus = 1.10 if promoter >= 50.0 else 1.0
        composite = ((growth_ranks[t] + inst_ranks[t] + vol_ranks[t] + roce_ranks[t]) / 4.0) * bonus
        scores[t] = min(1.0, round(composite, 4))

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_varsity_intensity(
    stage1_tickers: List[str],
    features_by_ticker: Dict[str, dict],
    sector_by_ticker: Dict[str, str],
    sector_percentiles: Optional[Dict[str, float]] = None,
) -> List[dict]:
    """
    Cross-Sectional Technical + Fundamental Confluence Percentile Composite for StockMinds Core / Varsity.
    - Factor 1: Volume Expansion (volume_surge)
    - Factor 2: Momentum Strength (rsi_14)
    - Factor 3: Capital Efficiency (roce_pct)
    - Factor 4: Prudent Solvency (inverse of debt_to_equity)
    - Factor 5: DCF Intrinsic Discount (dcf_discount_pct, neutral 0.50 median if None)
    - News catalyst multiplier: 10% bonus if news_sentiment > 0.10
    """
    if not stage1_tickers:
        return []

    vol_vals = [float(features_by_ticker[t].get("volume_surge") or 1.0) for t in stage1_tickers]
    rsi_vals = [float(features_by_ticker[t].get("rsi_14") or 50.0) for t in stage1_tickers]
    roce_vals = [float(features_by_ticker[t].get("roce_pct") or 12.0) for t in stage1_tickers]
    inv_de_vals = [1.0 / max(0.1, float(features_by_ticker[t].get("debt_to_equity") or 0.8)) for t in stage1_tickers]

    vol_ranks = pd.Series(vol_vals, index=stage1_tickers).rank(pct=True).to_dict()
    rsi_ranks = pd.Series(rsi_vals, index=stage1_tickers).rank(pct=True).to_dict()
    roce_ranks = pd.Series(roce_vals, index=stage1_tickers).rank(pct=True).to_dict()
    de_ranks = pd.Series(inv_de_vals, index=stage1_tickers).rank(pct=True).to_dict()

    # DCF discount percentile rank (tickers with valid DCF ranked amongst each other; missing gets neutral 0.50)
    dcf_tickers = [t for t in stage1_tickers if features_by_ticker[t].get("dcf_discount_pct") is not None]
    if dcf_tickers:
        dcf_vals = [float(features_by_ticker[t]["dcf_discount_pct"]) for t in dcf_tickers]
        dcf_ranks = pd.Series(dcf_vals, index=dcf_tickers).rank(pct=True).to_dict()
    else:
        dcf_ranks = {}

    scores = {}
    for t in stage1_tickers:
        tech_rank = 0.5 * vol_ranks[t] + 0.5 * rsi_ranks[t]
        t_dcf_rank = dcf_ranks.get(t, 0.50)
        fund_rank = (1.0 / 3.0) * roce_ranks[t] + (1.0 / 3.0) * de_ranks[t] + (1.0 / 3.0) * t_dcf_rank
        sentiment = float(features_by_ticker[t].get("news_sentiment") or 0.0)
        sentiment_bonus = 1.10 if sentiment > 0.10 else 1.0
        composite = ((tech_rank + fund_rank) / 2.0) * sentiment_bonus
        scores[t] = min(1.0, round(composite, 4))

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_fallback_intensity(
    stage1_tickers: List[str],
    features_by_ticker: Dict[str, dict],
    sector_by_ticker: Dict[str, str],
    sector_percentiles: Optional[Dict[str, float]] = None,
    sort_key: str = "simons_intensity",
) -> List[dict]:
    """Fallback ranking logic utilizing SORT_KEYS heuristic scoring for any custom strategy key."""
    if not stage1_tickers:
        return []

    sort_fn = SORT_KEYS.get(sort_key, score_simons)
    scored = []
    for t in stage1_tickers:
        raw_score = sort_fn(features_by_ticker[t])
        sector = sector_by_ticker.get(t, "UNKNOWN")
        pct = (sector_percentiles or {}).get(t, 50.0)
        if sector_percentiles is not None and raw_score > float("-inf"):
            adj_score = round(raw_score * (0.7 + 0.3 * (pct / 100.0)), 4)
        else:
            adj_score = raw_score
        scored.append({
            "ticker": t,
            "sector": sector,
            "intensity_score": adj_score,
            "raw_score": raw_score,
            "sector_percentile": round(pct, 2),
        })
    scored.sort(key=lambda row: row["intensity_score"], reverse=True)
    return scored


# Registry of Strategy Rankers by sort_key
STRATEGY_RANKERS: Dict[str, Callable] = {
    "simons_intensity": rank_simons_intensity,
    "lynch_intensity": rank_lynch_intensity,
    "marks_intensity": rank_marks_intensity,
    "rj_intensity": rank_rj_intensity,
    "varsity_intensity": rank_varsity_intensity,
}


def get_strategy_ranker(sort_key: str) -> Callable:
    """Returns the dedicated cross-sectional strategy ranker for a sort_key, or fallback."""
    if sort_key in STRATEGY_RANKERS:
        return STRATEGY_RANKERS[sort_key]
    return lambda stage1_tickers, features_by_ticker, sector_by_ticker, sector_percentiles=None: rank_fallback_intensity(
        stage1_tickers, features_by_ticker, sector_by_ticker, sector_percentiles=sector_percentiles, sort_key=sort_key
    )

