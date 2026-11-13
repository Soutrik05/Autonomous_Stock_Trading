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

from collections.abc import Callable

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
    """
    Multi-factor GARP standalone heuristic score for Peter Lynch (One Up On Wall Street, Ch. 7, 13).
    - Valuation Edge: PEG ratio (1/PEG)
    - Capital Productivity: ROCE
    - Cash Flow Reality: CFO/PAT
    - Balance Sheet: 1/DE
    - Growth Sweet-Spot: 15-28% Fast Grower bonus, >35% unsustainable penalty
    - Promoter Alignment: >= 50% skin in the game bonus
    """
    roce = features.get("roce_pct")
    if roce is None:
        return float("-inf")
    peg = features.get("peg")
    cfo = features.get("cfo_to_pat")
    de = features.get("debt_to_equity")
    pat_growth = float(features.get("pat_growth_yoy_pct") or 0.0)
    promoter = float(features.get("promoter_holding_pct") or 40.0)

    peg_val = max(0.05, float(peg)) if peg is not None and peg > 0 else 1.0
    cfo_val = min(2.0, max(0.1, float(cfo))) if cfo is not None else 1.0
    de_val = max(0.1, float(de)) if de is not None else 0.8

    # Category multiplier
    if 15.0 <= pat_growth <= 28.0:
        growth_mult = 1.15  # Fast Grower sweet spot
    elif 8.0 <= pat_growth < 15.0:
        growth_mult = 1.05  # Stalwart steady compounder
    elif pat_growth > 35.0:
        growth_mult = 0.85  # Unsustainable explosive growth warning
    else:
        growth_mult = 0.90  # Slow grower / sluggard

    promoter_bonus = 1.10 if promoter >= 50.0 else 1.0

    garp_score = (float(roce) / 15.0) * (1.0 / peg_val) * (cfo_val / 1.0) * (1.0 / de_val)
    return round(garp_score * growth_mult * promoter_bonus, 4)


def score_marks(features: dict) -> float:
    """
    Contrarian quality-oversold standalone heuristic score (Howard Marks Method A).
    Evaluates oversold momentum dislocation, valuation discount (P/E), and solvency moat (CFO / D/E).
    """
    rsi = features.get("rsi_14")
    if rsi is None:
        return float("-inf")
    rsi_val = float(rsi)
    # Higher score when RSI is depressed (<= 45)
    oversold_factor = max(0.1, (100.0 - rsi_val) / 50.0)

    pe = features.get("pe")
    pe_val = max(2.0, float(pe)) if pe is not None and float(pe) > 0 else 25.0
    val_factor = min(3.0, 25.0 / pe_val)

    roce = max(0.0, float(features.get("roce_pct") or 10.0))
    cfo = max(0.1, min(2.0, float(features.get("cfo_to_pat") or 1.0)))
    de = max(0.1, float(features.get("debt_to_equity") or 0.6))
    solvency_factor = (roce / 12.0) * (cfo / 1.0) * (0.8 / de)

    regime = str(features.get("regime") or "").upper()
    panic_mult = 1.25 if regime == "PANIC" else (1.10 if regime == "ELEVATED" else 1.0)
    score = (0.35 * oversold_factor + 0.35 * val_factor + 0.30 * solvency_factor) * panic_mult
    return round(score, 4)


def score_rj(features: dict) -> float:
    """
    Growth compounder standalone heuristic score for Rakesh Jhunjhunwala (Method A).
    Evaluates earnings growth velocity, capital productivity (ROCE), institutional accumulation,
    breakout volume, promoter skin-in-the-game, and valuation re-rating headroom.
    """
    volume_surge = features.get("volume_surge")
    if volume_surge is None:
        return float("-inf")
    pat_growth = max(0.0, float(features.get("pat_growth_yoy_pct") or 10.0))
    roce = max(0.0, float(features.get("roce_pct") or 15.0))
    inst_delta = float(features.get("fii_dii_qoq_delta_pct") or 0.0)
    promoter = float(features.get("promoter_holding_pct") or 40.0)
    pe = float(features.get("pe") or 25.0)

    promoter_bonus = 1.10 if promoter >= 50.0 else 1.0
    growth_bonus = 1.10 if pat_growth >= 25.0 else 1.0
    inst_mult = 1.0 + max(-0.2, min(0.3, inst_delta / 10.0))
    pe_factor = min(2.0, max(0.5, 30.0 / max(5.0, pe)))

    sentiment = float(features.get("news_sentiment") or 0.0)
    gov_mult = 0.85 if sentiment < -0.25 else 1.0

    score = (
        float(volume_surge)
        * (pat_growth / 15.0)
        * (roce / 15.0)
        * inst_mult
        * pe_factor
        * promoter_bonus
        * growth_bonus
        * gov_mult
    )
    return round(score, 4)


def score_varsity(features: dict) -> float:
    """
    Balanced technical and fundamental confluence heuristic score for Zerodha Varsity (Karthik Rangappa).
    - Technical: RSI momentum sweet spot (45-65, ideal 55-60), volume surge confirmation, trend efficiency.
    - Fundamental: ROCE capital productivity, prudent solvency (1/DE), DCF margin of safety.
    """
    rsi = features.get("rsi_14")
    if rsi is None:
        return float("-inf")
    rsi_val = float(rsi)
    # Penalize extreme overbought (> 72) or deeply broken (< 40)
    rsi_sweet_factor = max(0.2, 1.0 - (abs(rsi_val - 57.5) / 35.0))

    volume_surge = min(3.0, max(0.5, float(features.get("volume_surge") or 1.0)))
    ker = max(0.1, float(features.get("kaufman_er_20") or 0.30))
    roce = max(0.0, float(features.get("roce_pct") or 12.0))
    roe = max(0.0, float(features.get("roe_pct") or 12.0))
    de = max(0.1, float(features.get("debt_to_equity") or 0.8))

    sentiment = float(features.get("news_sentiment") or 0.0)
    sentiment_mult = 1.10 if sentiment > 0.10 else (0.85 if sentiment < -0.20 else 1.0)

    dcf = features.get("dcf_discount_pct")
    dcf_mult = 1.0 + max(-0.25, min(0.35, (dcf / 100.0))) if dcf is not None else 1.0

    tech_score = rsi_sweet_factor * (volume_surge / 1.0) * (ker / 0.30)
    fund_score = (roce / 15.0) * (roe / 15.0) * (1.0 / de) * dcf_mult
    return round((tech_score * 0.5 + fund_score * 0.5) * sentiment_mult, 4)


# Dictionary mapping persona sort keys to their heuristic scoring functions
SORT_KEYS: dict[str, Callable[[dict], float]] = {
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
    stage1_tickers: list[str],
    scores: dict[str, float],
    sector_by_ticker: dict[str, str],
    sector_percentiles: dict[str, float] | None = None,
) -> list[dict]:
    """Helper to format and sort candidate dictionary list by descending intensity."""
    scored = []
    for t in stage1_tickers:
        raw_score = scores[t]
        sector = sector_by_ticker.get(t, "UNKNOWN")
        pct = (sector_percentiles or {}).get(t, 50.0)
        scored.append(
            {
                "ticker": t,
                "sector": sector,
                "intensity_score": raw_score,
                "raw_score": raw_score,
                "sector_percentile": round(pct, 2),
            }
        )
    scored.sort(key=lambda row: row["intensity_score"], reverse=True)
    return scored


def rank_simons_intensity(
    stage1_tickers: list[str],
    features_by_ticker: dict[str, dict],
    sector_by_ticker: dict[str, str],
    sector_percentiles: dict[str, float] | None = None,
) -> list[dict]:
    """
    Cross-Sectional Percentile Rank Composite for Jim Simons (AQR / Renaissance Multi-Horizon Standard).
    - Factor 1: Volume Conviction (volume_surge) [25% weight]
    - Factor 2: Trend Efficiency (kaufman_er_20) [25% weight]
    - Factor 3: Directional Trend Strength (adx_14) [25% weight]
    - Factor 4: 52-Week Structural Momentum (dist_52w_high_pct) [25% weight] (George & Hwang 2004)
    - Directional consistency penalty: 20% discount if obv_slope_sign == -1
    """
    if not stage1_tickers:
        return []

    vol_vals = [float(features_by_ticker[t].get("volume_surge") or 1.0) for t in stage1_tickers]
    ker_vals = [float(features_by_ticker[t].get("kaufman_er_20") or 0.0) for t in stage1_tickers]
    adx_vals = [float(features_by_ticker[t].get("adx_14") or 0.0) for t in stage1_tickers]
    mom_vals = [
        float(features_by_ticker[t]["dist_52w_high_pct"])
        if features_by_ticker[t].get("dist_52w_high_pct") is not None
        else -50.0
        for t in stage1_tickers
    ]

    vol_ranks = pd.Series(vol_vals, index=stage1_tickers).rank(pct=True).to_dict()
    ker_ranks = pd.Series(ker_vals, index=stage1_tickers).rank(pct=True).to_dict()
    adx_ranks = pd.Series(adx_vals, index=stage1_tickers).rank(pct=True).to_dict()
    mom_ranks = pd.Series(mom_vals, index=stage1_tickers).rank(pct=True).to_dict()

    scores = {}
    for t in stage1_tickers:
        feat = features_by_ticker[t]
        obv_slope = feat.get("obv_slope_sign") or 0
        penalty = 0.8 if obv_slope < 0 else 1.0
        composite = ((vol_ranks[t] + ker_ranks[t] + adx_ranks[t] + mom_ranks[t]) / 4.0) * penalty
        scores[t] = round(composite, 4)

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_lynch_intensity(
    stage1_tickers: list[str],
    features_by_ticker: dict[str, dict],
    sector_by_ticker: dict[str, str],
    sector_percentiles: dict[str, float] | None = None,
) -> list[dict]:
    """
    Cross-Sectional 5-Factor GARP Percentile Composite for Peter Lynch (One Up On Wall Street).
    - Factor 1 (30%): Valuation Edge (lower PEG is better -> rank inverse of peg)
    - Factor 2 (25%): Capital Productivity (higher ROCE is better)
    - Factor 3 (20%): Cash Conversion Reality (higher CFO/PAT is better)
    - Factor 4 (15%): Balance Sheet Fortitude (lower Debt-to-Equity is better -> rank inverse of DE)
    - Factor 5 (10%): Institutional Under-Ownership Runway (lower FII+DII is better -> rank inverse of Inst)
    - Growth Category Multipliers:
      - Fast Grower (15% <= YoY PAT growth <= 28%): +15% bonus
      - Stalwart (8% <= YoY PAT growth < 15%): +5% bonus
      - Speculative / Unsustainable (YoY PAT growth > 35% or < 8%): -15% penalty
    - Promoter Skin-in-the-game: +10% bonus if promoter_holding_pct >= 50.0%
    """
    if not stage1_tickers:
        return []

    inv_peg_vals = [1.0 / max(0.05, float(features_by_ticker[t].get("peg") or 1.0)) for t in stage1_tickers]
    roce_vals = [float(features_by_ticker[t].get("roce_pct") or 12.0) for t in stage1_tickers]
    cfo_vals = [min(2.0, max(0.1, float(features_by_ticker[t].get("cfo_to_pat") or 0.8))) for t in stage1_tickers]
    inv_de_vals = [1.0 / max(0.1, float(features_by_ticker[t].get("debt_to_equity") or 0.8)) for t in stage1_tickers]

    def _inst_holding(t: str) -> float:
        fii = float(features_by_ticker[t].get("fii_holding_pct") or 0.0)
        dii = float(features_by_ticker[t].get("dii_holding_pct") or 0.0)
        return fii + dii

    inv_inst_vals = [1.0 / max(5.0, _inst_holding(t)) for t in stage1_tickers]

    peg_ranks = pd.Series(inv_peg_vals, index=stage1_tickers).rank(pct=True).to_dict()
    roce_ranks = pd.Series(roce_vals, index=stage1_tickers).rank(pct=True).to_dict()
    cfo_ranks = pd.Series(cfo_vals, index=stage1_tickers).rank(pct=True).to_dict()
    de_ranks = pd.Series(inv_de_vals, index=stage1_tickers).rank(pct=True).to_dict()
    inst_ranks = pd.Series(inv_inst_vals, index=stage1_tickers).rank(pct=True).to_dict()

    scores = {}
    for t in stage1_tickers:
        pat_growth = float(features_by_ticker[t].get("pat_growth_yoy_pct") or 0.0)
        promoter = float(features_by_ticker[t].get("promoter_holding_pct") or 40.0)

        if 15.0 <= pat_growth <= 28.0:
            growth_mult = 1.15  # Fast Grower
        elif 8.0 <= pat_growth < 15.0:
            growth_mult = 1.05  # Stalwart
        elif pat_growth > 35.0:
            growth_mult = 0.85  # Unsustainable jump
        else:
            growth_mult = 0.90  # Sluggard / Slow Grower

        promoter_mult = 1.10 if promoter >= 50.0 else 1.0

        composite = (
            0.30 * peg_ranks[t] + 0.25 * roce_ranks[t] + 0.20 * cfo_ranks[t] + 0.15 * de_ranks[t] + 0.10 * inst_ranks[t]
        )
        scores[t] = min(1.0, round(composite * growth_mult * promoter_mult, 4))

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_marks_intensity(
    stage1_tickers: list[str],
    features_by_ticker: dict[str, dict],
    sector_by_ticker: dict[str, str],
    sector_percentiles: dict[str, float] | None = None,
) -> list[dict]:
    """
    Cross-Sectional 5-Factor Contrarian Percentile Composite for Howard Marks (Method A).
    Grounded in The Most Important Thing (Ch. 1, 3, 5, 8, 9, 11).
    - Factor 1 (30%): Sentiment Dislocation / Oversold (100 - RSI-14 and proximity to 52w low)
    - Factor 2 (25%): Valuation Margin of Safety (inverse P/E and DCF discount)
    - Factor 3 (25%): Balance Sheet Solvency Moat (inverse D/E and ROCE capital productivity)
    - Factor 4 (20%): Cash Flow Reality Check (CFO/PAT cash realization)
    - Multipliers:
      - Macro Panic: PANIC -> 1.25x, ELEVATED -> 1.10x, NORMAL -> 1.0x
      - Governance Risk: 0.85x discount if news_sentiment < -0.25
    """
    if not stage1_tickers:
        return []

    # Factor 1: Dislocation / Oversold
    rsi_inv = [100.0 - float(features_by_ticker[t].get("rsi_14") or 50.0) for t in stage1_tickers]
    dist_inv = [-float(features_by_ticker[t].get("dist_52w_low_pct") or 20.0) for t in stage1_tickers]

    # Factor 2: Valuation Margin of Safety (lower P/E is better; DCF discount bonus)
    inv_pe = [
        1.0 / max(2.0, float(features_by_ticker[t].get("pe") or 25.0))
        if features_by_ticker[t].get("pe") is not None and float(features_by_ticker[t].get("pe") or 0) > 0
        else 0.04
        for t in stage1_tickers
    ]

    # Factor 3: Balance Sheet Solvency Moat (lower D/E, higher ROCE)
    inv_de = [1.0 / max(0.1, float(features_by_ticker[t].get("debt_to_equity") or 0.6)) for t in stage1_tickers]
    roce_vals = [float(features_by_ticker[t].get("roce_pct") or 10.0) for t in stage1_tickers]

    # Factor 4: Cash Flow Reality Check
    cfo_vals = [min(2.5, max(0.1, float(features_by_ticker[t].get("cfo_to_pat") or 0.8))) for t in stage1_tickers]

    rsi_ranks = pd.Series(rsi_inv, index=stage1_tickers).rank(pct=True).to_dict()
    dist_ranks = pd.Series(dist_inv, index=stage1_tickers).rank(pct=True).to_dict()
    pe_ranks = pd.Series(inv_pe, index=stage1_tickers).rank(pct=True).to_dict()
    de_ranks = pd.Series(inv_de, index=stage1_tickers).rank(pct=True).to_dict()
    roce_ranks = pd.Series(roce_vals, index=stage1_tickers).rank(pct=True).to_dict()
    cfo_ranks = pd.Series(cfo_vals, index=stage1_tickers).rank(pct=True).to_dict()

    scores = {}
    for t in stage1_tickers:
        feat = features_by_ticker[t]
        oversold_rank = 0.60 * rsi_ranks[t] + 0.40 * dist_ranks[t]
        val_rank = pe_ranks[t]
        dcf = feat.get("dcf_discount_pct")
        if dcf is not None and float(dcf) > 0:
            val_rank = min(1.0, val_rank * 1.15)  # DCF margin of safety bonus

        solvency_rank = 0.60 * de_ranks[t] + 0.40 * roce_ranks[t]
        cash_rank = cfo_ranks[t]

        raw_composite = 0.30 * oversold_rank + 0.25 * val_rank + 0.25 * solvency_rank + 0.20 * cash_rank

        regime = str(feat.get("regime") or "").upper()
        panic_mult = 1.25 if regime == "PANIC" else (1.10 if regime == "ELEVATED" else 1.0)

        sentiment = float(feat.get("news_sentiment") or 0.0)
        gov_mult = 0.85 if sentiment < -0.25 else 1.0

        composite = raw_composite * panic_mult * gov_mult
        scores[t] = min(1.0, round(composite, 4))

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_rj_intensity(
    stage1_tickers: list[str],
    features_by_ticker: dict[str, dict],
    sector_by_ticker: dict[str, str],
    sector_percentiles: dict[str, float] | None = None,
) -> list[dict]:
    """
    Cross-Sectional Growth Compounder 5-Factor Percentile Composite for Rakesh Jhunjhunwala (Method A).
    Grounded in Rare Enterprises compounder tenets:
    - Factor 1 (30%): Earnings Growth Velocity (pat_growth_yoy_pct)
    - Factor 2 (25%): Capital Return Efficiency (roce_pct)
    - Factor 3 (20%): Institutional Footprint / Accumulation (fii_dii_qoq_delta_pct)
    - Factor 4 (15%): Breakout Volume Conviction (volume_surge)
    - Factor 5 (10%): Valuation Re-Rating Multiple (1 / P/E multiple)
    - Multipliers:
      - Promoter Skin-in-the-Game: 1.10x if promoter_holding_pct >= 50.0%
      - Operating Leverage Acceleration: 1.10x if pat_growth_yoy_pct >= 25.0%
      - Governance Risk Discount: 0.85x if news_sentiment < -0.25
    """
    if not stage1_tickers:
        return []

    growth_vals = [float(features_by_ticker[t].get("pat_growth_yoy_pct") or 0.0) for t in stage1_tickers]
    roce_vals = [float(features_by_ticker[t].get("roce_pct") or 15.0) for t in stage1_tickers]
    inst_vals = [float(features_by_ticker[t].get("fii_dii_qoq_delta_pct") or 0.0) for t in stage1_tickers]
    vol_vals = [float(features_by_ticker[t].get("volume_surge") or 1.0) for t in stage1_tickers]
    inv_pe_vals = [
        1.0 / max(5.0, float(features_by_ticker[t].get("pe") or 30.0))
        if features_by_ticker[t].get("pe") is not None and float(features_by_ticker[t].get("pe") or 0) > 0
        else 0.033
        for t in stage1_tickers
    ]

    growth_ranks = pd.Series(growth_vals, index=stage1_tickers).rank(pct=True).to_dict()
    roce_ranks = pd.Series(roce_vals, index=stage1_tickers).rank(pct=True).to_dict()
    inst_ranks = pd.Series(inst_vals, index=stage1_tickers).rank(pct=True).to_dict()
    vol_ranks = pd.Series(vol_vals, index=stage1_tickers).rank(pct=True).to_dict()
    pe_ranks = pd.Series(inv_pe_vals, index=stage1_tickers).rank(pct=True).to_dict()

    scores = {}
    for t in stage1_tickers:
        feat = features_by_ticker[t]
        raw_composite = (
            0.30 * growth_ranks[t]
            + 0.25 * roce_ranks[t]
            + 0.20 * inst_ranks[t]
            + 0.15 * vol_ranks[t]
            + 0.10 * pe_ranks[t]
        )
        promoter = float(feat.get("promoter_holding_pct") or 0.0)
        promoter_bonus = 1.10 if promoter >= 50.0 else 1.0

        pat_growth = float(feat.get("pat_growth_yoy_pct") or 0.0)
        op_leverage_bonus = 1.10 if pat_growth >= 25.0 else 1.0

        sentiment = float(feat.get("news_sentiment") or 0.0)
        gov_mult = 0.85 if sentiment < -0.25 else 1.0

        composite = raw_composite * promoter_bonus * op_leverage_bonus * gov_mult
        scores[t] = min(1.0, round(composite, 4))

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_varsity_intensity(
    stage1_tickers: list[str],
    features_by_ticker: dict[str, dict],
    sector_by_ticker: dict[str, str],
    sector_percentiles: dict[str, float] | None = None,
) -> list[dict]:
    """
    Balanced 50/50 Technical + Fundamental Confluence Percentile Composite for StockMinds Core / Varsity.
    Authentically grounded in Zerodha Varsity (Karthik Rangappa, Modules 2, 3, 9):
    - Technical Confluence (50%):
      - Factor 1: Volume Surge Expansion (40% of tech = 20% total)
      - Factor 2: RSI Momentum Sweet Spot in 45-65 zone, peak at 57.5 (40% of tech = 20% total)
      - Factor 3: Kaufman Trend Efficiency Ratio (20% of tech = 10% total)
    - Fundamental Confluence (50%):
      - Factor 4: Capital Productivity ROCE (40% of fund = 20% total)
      - Factor 5: Balance Sheet Solvency (1/DE) (30% of fund = 15% total)
      - Factor 6: DCF Intrinsic Margin of Safety (30% of fund = 15% total; neutral 0.50 for financials/missing)
    - Catalyst Multiplier:
      - +10% bonus if news_sentiment > 0.10 (order wins, earnings beats)
      - -15% penalty if news_sentiment < -0.20 (regulatory, governance distress)
    """
    if not stage1_tickers:
        return []

    vol_vals = [float(features_by_ticker[t].get("volume_surge") or 1.0) for t in stage1_tickers]
    # RSI sweet-spot: optimal entry around 57.5, penalize deviation in either direction
    rsi_sweet_vals = [-abs(float(features_by_ticker[t].get("rsi_14") or 50.0) - 57.5) for t in stage1_tickers]
    ker_vals = [float(features_by_ticker[t].get("kaufman_er_20") or 0.30) for t in stage1_tickers]

    roce_vals = [float(features_by_ticker[t].get("roce_pct") or 12.0) for t in stage1_tickers]
    inv_de_vals = [1.0 / max(0.1, float(features_by_ticker[t].get("debt_to_equity") or 0.8)) for t in stage1_tickers]

    vol_ranks = pd.Series(vol_vals, index=stage1_tickers).rank(pct=True).to_dict()
    rsi_sweet_ranks = pd.Series(rsi_sweet_vals, index=stage1_tickers).rank(pct=True).to_dict()
    ker_ranks = pd.Series(ker_vals, index=stage1_tickers).rank(pct=True).to_dict()

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
        # 50% Technical Composite: 40% Volume, 40% RSI Sweet Spot, 20% KER Efficiency
        tech_rank = 0.40 * vol_ranks[t] + 0.40 * rsi_sweet_ranks[t] + 0.20 * ker_ranks[t]

        # 50% Fundamental Composite: 40% ROCE, 30% Solvency (1/DE), 30% DCF Margin of Safety
        t_dcf_rank = dcf_ranks.get(t, 0.50)
        fund_rank = 0.40 * roce_ranks[t] + 0.30 * de_ranks[t] + 0.30 * t_dcf_rank

        sentiment = float(features_by_ticker[t].get("news_sentiment") or 0.0)
        if sentiment > 0.10:
            sentiment_mult = 1.10
        elif sentiment < -0.20:
            sentiment_mult = 0.85
        else:
            sentiment_mult = 1.0

        composite = (0.50 * tech_rank + 0.50 * fund_rank) * sentiment_mult
        scores[t] = min(1.0, round(composite, 4))

    return _format_scored_candidates(stage1_tickers, scores, sector_by_ticker, sector_percentiles)


def rank_fallback_intensity(
    stage1_tickers: list[str],
    features_by_ticker: dict[str, dict],
    sector_by_ticker: dict[str, str],
    sector_percentiles: dict[str, float] | None = None,
    sort_key: str = "simons_intensity",
) -> list[dict]:
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
        scored.append(
            {
                "ticker": t,
                "sector": sector,
                "intensity_score": adj_score,
                "raw_score": raw_score,
                "sector_percentile": round(pct, 2),
            }
        )
    scored.sort(key=lambda row: row["intensity_score"], reverse=True)
    return scored


# Registry of Strategy Rankers by sort_key
STRATEGY_RANKERS: dict[str, Callable] = {
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
    return lambda stage1_tickers, features_by_ticker, sector_by_ticker, sector_percentiles=None: (
        rank_fallback_intensity(
            stage1_tickers,
            features_by_ticker,
            sector_by_ticker,
            sector_percentiles=sector_percentiles,
            sort_key=sort_key,
        )
    )
