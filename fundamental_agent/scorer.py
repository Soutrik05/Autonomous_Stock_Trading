# ============================================================
# fundamental_agent/scorer.py
#
# All scoring logic for the fundamental agent.
# Takes raw fetched data and returns scored output.
#
# Two public functions:
#   compute_score(raw)  → scored dict (final_score, metric_scores,
#                          weights_used, confidence, flags, sector_scoring)
#
# Scoring philosophy (from Zerodha Varsity Module 3):
#   - ROE and PAT margin are scored RELATIVE to sector benchmarks.
#     "Ratios only make sense when compared to peers in the same
#     industry." A 10% ROE is poor for IT (median 30%) but decent
#     for Energy (median 12%).
#   - All other metrics (PE, PB, D/E, EPS growth, FCF) use universal
#     bands since they don't have the same sector-dependency.
#   - PE is excluded from scoring entirely when flagged unreliable;
#     its weight is redistributed to other metrics.
# ============================================================

import logging
from typing import Any, Dict, Optional

from fundamental_agent import config as cfg

logger = logging.getLogger("fundamental_agent.scorer")


# ============================================================
# SECTION 1 — Band Scoring Primitives
# ============================================================

def _score_from_bands(value: float, bands: list, higher_is_better: bool = True) -> int:
    """
    Generic threshold-band scorer. Returns 0–100.

    higher_is_better=True  → used for ROE, PAT margin, EPS growth, FCF.
                              Iterates bands from highest threshold down.
    higher_is_better=False → used for PE, PB, D/E (lower is better).
                              Iterates bands from lowest threshold up.

    Args:
        value:            The metric value to score.
        bands:            List of (threshold, score) tuples.
        higher_is_better: Scoring direction.

    Returns 0 if no band matches (value below all thresholds when
    higher_is_better, or above all thresholds when not).
    """
    if higher_is_better:
        for threshold, score in sorted(bands, key=lambda x: x[0], reverse=True):
            if value >= threshold:
                return score
        return 0
    else:
        for threshold, score in sorted(bands, key=lambda x: x[0]):
            if value <= threshold:
                return score
        return 0


def _score_sector_relative(
    value:  float,
    median: float,
    low:    float,
    high:   float,
) -> int:
    """
    Scores a metric relative to its sector's benchmark range.

    Uses a 9-level scale anchored to sector median, low, and high:
        ≥ 2× high     → 100  (exceptional outlier)
        ≥ 1.3× high   → 90   (well above sector top)
        ≥ high        → 80   (at top of normal sector range)
        ≥ 1.2× median → 70   (comfortably above sector median)
        ≥ median      → 55   (at sector median — fair)
        ≥ 0.8× median → 45   (slightly below median)
        ≥ low         → 30   (at bottom of normal sector range)
        ≥ 0.5× low    → 15   (below sector norms)
        < 0.5× low    → 5    (well below sector norms)

    Rationale for relative scoring:
        A steel company (Basic Materials) with ROE=12% is at sector
        median and should score ~55. With universal thresholds (15%
        target), it would score 35, which misrepresents its quality.
        Relative scoring prevents structural sector penalisation.
    """
    if value >= high * 2.0:    return 100
    if value >= high * 1.3:    return 90
    if value >= high:          return 80
    if value >= median * 1.2:  return 70
    if value >= median:        return 55
    if value >= median * 0.8:  return 45
    if value >= low:           return 30
    if value >= low * 0.5:     return 15
    return 5


# ============================================================
# SECTION 2 — Per-Metric Scorers
# ============================================================

def score_pe(pe: Optional[float]) -> int:
    if pe is None or pe <= 0:
        return cfg.SCORE_UNAVAILABLE_PENALTY
    return _score_from_bands(pe, cfg.PE_SCORE_BANDS, higher_is_better=False)


def score_pb(pb: Optional[float]) -> int:
    if pb is None or pb <= 0:
        return cfg.SCORE_UNAVAILABLE_PENALTY
    return _score_from_bands(pb, cfg.PB_SCORE_BANDS, higher_is_better=False)


def score_de(de: Optional[float]) -> int:
    if de is None:
        return cfg.SCORE_UNAVAILABLE_PENALTY
    return _score_from_bands(de, cfg.DE_SCORE_BANDS, higher_is_better=False)


def score_roe(roe_pct: Optional[float], sector: Optional[str]) -> int:
    """
    Scores ROE relative to sector benchmarks when available.
    Falls back to universal bands when sector is unknown.
    roe_pct must already be multiplied by 100 (e.g. 18.5, not 0.185).
    """
    if roe_pct is None:
        return cfg.SCORE_UNAVAILABLE_PENALTY
    bench = cfg.SECTOR_BENCHMARKS.get(sector) if sector else None
    if bench:
        return _score_sector_relative(
            roe_pct,
            bench["roe_median"],
            bench["roe_range"][0],
            bench["roe_range"][1],
        )
    return _score_from_bands(roe_pct, cfg.ROE_SCORE_BANDS_UNIVERSAL, higher_is_better=True)


def score_pat_margin(pat_pct: Optional[float], sector: Optional[str]) -> int:
    """
    Scores PAT margin relative to sector benchmarks when available.
    Falls back to universal bands when sector is unknown.
    pat_pct must already be multiplied by 100 (e.g. 18.5, not 0.185).
    """
    if pat_pct is None:
        return cfg.SCORE_UNAVAILABLE_PENALTY
    bench = cfg.SECTOR_BENCHMARKS.get(sector) if sector else None
    if bench:
        return _score_sector_relative(
            pat_pct,
            bench["pat_median"],
            bench["pat_range"][0],
            bench["pat_range"][1],
        )
    return _score_from_bands(pat_pct, cfg.PAT_MARGIN_SCORE_BANDS_UNIVERSAL, higher_is_better=True)


def score_eps_growth(growth_pct: Optional[float]) -> int:
    if growth_pct is None:
        return cfg.SCORE_UNAVAILABLE_PENALTY
    return _score_from_bands(growth_pct, cfg.EPS_GROWTH_SCORE_BANDS, higher_is_better=True)


def score_fcf(fcf_raw: Optional[float]) -> int:
    """
    Scores FCF. fcf_raw is in raw INR units.
    Converts to Crores (divides by 1e7) before applying bands,
    since FCF_SCORE_BANDS thresholds are in Crores.
    """
    if fcf_raw is None:
        return cfg.SCORE_UNAVAILABLE_PENALTY
    return _score_from_bands(fcf_raw / 1e7, cfg.FCF_SCORE_BANDS, higher_is_better=True)


# ============================================================
# SECTION 3 — Flag Builder
# ============================================================

def _build_flags(raw: Dict[str, Any], bench: Optional[Dict]) -> list:
    """
    Builds the list of human-readable flag strings for a stock.

    Flags are informational — they surface notable signals and
    data quality warnings for the LLM layer and the output layer.
    They do not affect the score.

    Categories:
        WARNING:  Data quality issues the user should be aware of.
        NOTE:     Interesting signals that need context to interpret.
        Positive: Strong metric observations (no prefix).
    """
    flags = []
    sector = raw.get("sector")

    # ── Data quality warnings ────────────────────────────────
    if raw.get("pe_unreliable"):
        flags.append("WARNING: PE unreliable (>200x or <1x) — excluded from scoring")
    if raw.get("pe_divergence"):
        flags.append("NOTE: PE divergence detected — using yfinance trailingPE")

    # ── Sector context (always present) ─────────────────────
    if bench:
        flags.append(
            f"Sector: {sector} "
            f"(ROE median {bench['roe_median']}%, PAT median {bench['pat_median']}%)"
        )
    else:
        flags.append("Sector: Unknown (universal benchmarks used)")

    # ── ROE signals ──────────────────────────────────────────
    roe = raw.get("roe")
    if roe is not None:
        if bench and roe > bench["roe_range"][1] / 100:
            flags.append(
                f"High ROE vs sector ({roe * 100:.1f}% vs sector top {bench['roe_range'][1]}%)"
            )
        elif not bench and roe > 0.20:
            flags.append(f"High ROE ({roe * 100:.1f}%)")

    # ── PAT margin signals ───────────────────────────────────
    pat = raw.get("pat_margin")
    if pat is not None:
        if bench and pat > bench["pat_range"][1] / 100:
            flags.append(
                f"Strong PAT margin vs sector "
                f"({pat * 100:.1f}% vs sector top {bench['pat_range'][1]}%)"
            )
        elif not bench and pat > 0.20:
            flags.append(f"Strong PAT margin ({pat * 100:.1f}%)")

    # ── Debt signal ──────────────────────────────────────────
    de = raw.get("de")
    if de is not None and de < 0.5:
        flags.append("Low debt (D/E < 0.5)")

    # ── EPS growth signals ───────────────────────────────────
    eps_g = raw.get("eps_growth_pct")
    if eps_g is not None:
        if eps_g > 20:
            flags.append(f"Strong EPS growth ({eps_g:.1f}%)")
        if eps_g < -30:
            flags.append(
                f"WARNING: EPS growth {eps_g:.1f}% — possible corporate action "
                f"(demerger / restructuring) distorting base year. Verify on Screener."
            )

    # ── FCF signals ──────────────────────────────────────────
    fcf    = raw.get("fcf")
    op_cf  = raw.get("operating_cf")
    capex  = raw.get("capex")
    if fcf is not None and fcf > 0:
        flags.append("Positive FCF")
    if op_cf is not None and capex is not None and fcf is not None and fcf > 0:
        op_cf_cr = op_cf / 1e7
        if op_cf_cr < 500:
            flags.append(
                f"NOTE: FCF positive but Op CF only ₹{op_cf_cr:.0f} Cr "
                f"— verify CapEx classification (some capex may be in working capital)"
            )

    # ── Valuation signal ─────────────────────────────────────
    pe = raw.get("pe")
    if pe is not None and pe < 15:
        flags.append(f"Attractive valuation (PE {pe:.1f}x)")

    return flags


# ============================================================
# SECTION 4 — Main Scoring Entry Point
# ============================================================

def compute_score(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes the full scored output for one stock from its raw fetched data.

    Steps:
        1. Convert raw ROE and PAT margin to percentage scale.
        2. Score each metric individually (0–100).
        3. If PE is unreliable, zero out its weight and redistribute
           to PB, ROE, and EPS growth (as configured in config.py).
        4. Compute weighted final score.
        5. Compute confidence (penalised for unavailable metrics).
        6. Build flags.

    Args:
        raw: Output dict from fetcher.fetch_stock_data().

    Returns:
        Dict with keys: final_score, metric_scores, weights_used,
        confidence, flags, sector, sector_scoring.
    """
    sector         = raw.get("sector")
    roe_pct        = round(raw["roe"] * 100, 2)        if raw.get("roe")        is not None else None
    pat_margin_pct = round(raw["pat_margin"] * 100, 2) if raw.get("pat_margin") is not None else None

    # ── Per-metric scores ────────────────────────────────────
    metric_scores = {
        "pe":         score_pe(raw.get("pe")),
        "pb":         score_pb(raw.get("pb")),
        "roe":        score_roe(roe_pct, sector),
        "de":         score_de(raw.get("de")),
        "pat_margin": score_pat_margin(pat_margin_pct, sector),
        "eps_growth": score_eps_growth(raw.get("eps_growth_pct")),
        "fcf":        score_fcf(raw.get("fcf")),
    }

    # ── Weight adjustment if PE unreliable ───────────────────
    weights = dict(cfg.METRIC_WEIGHTS)
    if raw.get("pe_unreliable"):
        weights["pe"] = 0.0
        for metric, extra in cfg.PE_FALLBACK_WEIGHT_REDISTRIBUTION.items():
            weights[metric] += extra

    # ── Final weighted score ─────────────────────────────────
    final_score = sum(metric_scores[m] * weights[m] for m in metric_scores)

    # ── Confidence (decreases as more metrics are unavailable) ─
    unavailable = sum(
        1 for s in metric_scores.values()
        if s == cfg.SCORE_UNAVAILABLE_PENALTY
    )
    confidence = max(0.3, 1.0 - unavailable * 0.08)

    # ── Sector context for flags ─────────────────────────────
    bench = cfg.SECTOR_BENCHMARKS.get(sector) if sector else None

    return {
        "final_score":    round(final_score, 1),
        "metric_scores":  metric_scores,
        "weights_used":   {k: round(v, 4) for k, v in weights.items()},
        "confidence":     round(confidence, 2),
        "flags":          _build_flags(raw, bench),
        "sector":         sector,
        "sector_scoring": "relative" if bench else "universal",
    }
