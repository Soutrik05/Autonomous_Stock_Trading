# ============================================================
# config.py — Fundamental Agent Configuration (Data-Tuned)
# ============================================================

# ── Core Data Settings ──────────────────────────────────────
NSE_SUFFIX = ".NS"
QUARTERLY_HISTORY_PERIODS = 4
SCORE_UNAVAILABLE_PENALTY = 20

# ── Screener Cache Settings ─────────────────────────────────
SCREENER_CACHE_TTL_HOURS = 336  # 14 days

# ── Hard Disqualification Filters ───────────────────────────
HARD_FILTERS = {
    "max_debt_equity": 5.0,           # Ignored for ASSET_HEAVY_SECTORS
    "min_negative_eps_quarters": 4,   # 4 consecutive quarters of losses = reject
    "min_roe": 0.0,                   # Negative ROE = reject
}

# ── Sector Mappings ─────────────────────────────────────────
# Official NSE Asset-Heavy / Capex-Heavy Sectors
ASSET_HEAVY_SECTORS = {
    "Capital Goods",
    "Construction Materials",
    "Construction",
    "Power",
    "Metals & Mining",
    "Oil Gas & Consumable Fuels",
    "Automobile and Auto Components",
    "Telecommunication"
}

# ── Tier & Metric Weights ───────────────────────────────────
TIER_WEIGHTS = {
    "growth":    0.25,
    "quality":   0.35,
    "valuation": 0.20,
    "moat":      0.20,
}

TIER_CONFIDENCE_THRESHOLD = 0.40

GROWTH_WEIGHTS = {
    "revenue_cagr_3yr": 0.30, 
    "profit_cagr_3yr":  0.40, 
    "eps_growth_1yr":   0.30
}

QUALITY_WEIGHTS = {
    "roe_or_roce": 0.35, 
    "pat_margin":  0.25, 
    "fcf":         0.25, 
    "de":          0.15
}

VALUATION_WEIGHTS = {
    "pe_vs_sector": 0.60, 
    "pb":           0.40
}

MOAT_WEIGHTS = {
    "gpm": 0.40, 
    "opm": 0.30, 
    "receivables_pct_sales": 0.30 
}

# ── Scoring Bounds (Tuned to Nifty 500 Reality) ───
SCORING_BOUNDS = {
    "revenue_cagr_3yr":      (2.5, 25.0),   
    "profit_cagr_3yr":       (2.6, 32.2),   
    "eps_growth_1yr":        (2.5, 30.0),   
    "fcf_crores":            (-500, 5000),  
    "pb":                    (5.0, 1.0),    
    "gpm":                   (0.0, 40.0),   
    "opm":                   (0.0, 25.0),   
    "receivables_pct_sales": (35.0, 5.0),   
}

LEVERAGE_EFFICIENCY_BASELINE_ROCE = 12.0 

# ── Growth Guards ───────────────────────────────────────────
CAGR_MAX_CLIP = 50.0  
CAGR_YEARS = 3        

# ── PE Reliability & Sanity Checks ──────────────────────────
PE_UNRELIABLE_THRESHOLD = 200
PE_DIVERGENCE_WARN_PCT = 40
PE_MIN_PLAUSIBLE = 0.5  
PE_EPS_SANITY_CHECK = True  
EPS_GROWTH_MAX_RATIO = 50.0

# ── Threshold settings ──────────────────────────
# The minimum fundamental score required for a stock to pass, 
# based on the user's selected risk profile.
# Low Risk = Must have pristine fundamentals (0.75+)
# High Risk = Willing to accept lower quality for growth/momentum (0.40+)

DEFAULT_RISK_PROFILE = "medium"
RISK_THRESHOLDS = {
    "low": 0.75,
    "medium": 0.60,
    "high": 0.40
}

# ── Orchestrator Output Settings ────────────────────────────
ORCHESTRATOR_OUTPUT_DIR = "results/fundamental_runs"

# ── Sector Benchmarks ────────
SECTOR_BENCHMARKS = {
    "Automobile and Auto Components": {
        "roe_median":  14.8, "roe_range": ( 12.1,  18.6),
        "pat_median":   6.8, "pat_range": (  4.8,  12.2),
        "pe_median":   35.4, "pe_range":  ( 26.5,  51.2),
    },
    "Capital Goods": {
        "roe_median":  17.1, "roe_range": ( 12.6,  23.1),
        "pat_median":  11.6, "pat_range": (  7.6,  16.8),
        "pe_median":   40.9, "pe_range":  ( 27.8,  57.2),
    },
    "Chemicals": {
        "roe_median":  13.4, "roe_range": (  8.9,  17.6),
        "pat_median":   9.8, "pat_range": (  4.7,  16.2),
        "pe_median":   37.2, "pe_range":  ( 30.8,  56.7),
    },
    "Construction": {
        "roe_median":  12.4, "roe_range": ( 11.2,  15.2),
        "pat_median":   5.7, "pat_range": (  3.6,  12.7),
        "pe_median":   22.3, "pe_range":  ( 19.8,  29.8),
    },
    "Construction Materials": {
        "roe_median":   5.3, "roe_range": (  4.0,   9.3),
        "pat_median":   8.1, "pat_range": (  6.5,   8.9),
        "pe_median":   38.7, "pe_range":  ( 28.2,  42.5),
    },
    "Consumer Durables": {
        "roe_median":  17.4, "roe_range": ( 14.2,  20.6),
        "pat_median":   5.1, "pat_range": (  4.1,   8.1),
        "pe_median":   47.3, "pe_range":  ( 35.1,  58.8),
    },
    "Consumer Services": {
        "roe_median":  11.8, "roe_range": (  5.3,  23.1),
        "pat_median":  15.5, "pat_range": (  4.3,  22.3),
        "pe_median":   46.4, "pe_range":  ( 29.4,  66.9),
    },
    "Diversified": {
        "roe_median":   9.6, "roe_range": (  9.2,  20.1),
        "pat_median":   5.0, "pat_range": (  4.6,   6.4),
        "pe_median":   27.0, "pe_range":  ( 26.0,  42.8),
    },
    "Fast Moving Consumer Goods": {
        "roe_median":  17.0, "roe_range": ( 12.8,  22.0),
        "pat_median":  10.8, "pat_range": (  6.4,  14.7),
        "pe_median":   43.3, "pe_range":  ( 23.7,  59.3),
    },
    "Financial Services": {
        "roe_median":  15.8, "roe_range": ( 11.0,  20.9),
        "pat_median":  33.5, "pat_range": ( 22.2,  50.3),
        "pe_median":   19.6, "pe_range":  ( 12.2,  35.5),
    },
    "Healthcare": {
        "roe_median":  16.5, "roe_range": ( 11.4,  20.1),
        "pat_median":  13.5, "pat_range": (  9.3,  19.1),
        "pe_median":   41.2, "pe_range":  ( 28.5,  62.8),
    },
    "Information Technology": {
        "roe_median":  19.0, "roe_range": ( 14.8,  26.7),
        "pat_median":  12.4, "pat_range": ( 10.0,  16.5),
        "pe_median":   24.3, "pe_range":  ( 18.8,  32.4),
    },
    "Media Entertainment & Publication": {
        "roe_median":  12.5, "roe_range": (  9.6,  14.1),
        "pat_median":  20.4, "pat_range": ( 13.6,  28.1),
        "pe_median":   14.8, "pe_range":  ( 13.8,  24.0),
    },
    "Metals & Mining": {
        "roe_median":  15.1, "roe_range": (  9.3,  25.6),
        "pat_median":   9.3, "pat_range": (  4.2,  24.9),
        "pe_median":   24.5, "pe_range":  ( 18.3,  31.5),
    },
    "Oil Gas & Consumable Fuels": {
        "roe_median":  13.6, "roe_range": (  9.0,  16.7),
        "pat_median":   7.7, "pat_range": (  5.6,  11.1),
        "pe_median":   11.6, "pe_range":  (  9.0,  18.5),
    },
    "Power": {
        "roe_median":  12.1, "roe_range": (  7.5,  15.0),
        "pat_median":  16.0, "pat_range": ( 11.2,  21.8),
        "pe_median":   24.6, "pe_range":  ( 16.9,  37.5),
    },
    "Realty": {
        "roe_median":  11.2, "roe_range": (  9.1,  14.7),
        "pat_median":  21.2, "pat_range": ( 10.4,  37.6),
        "pe_median":   30.9, "pe_range":  ( 25.5,  53.6),
    },
    "Services": {
        "roe_median":  15.0, "roe_range": ( 10.8,  18.8),
        "pat_median":  17.1, "pat_range": (  4.2,  34.2),
        "pe_median":   26.5, "pe_range":  ( 21.0,  36.2),
    },
    "Telecommunication": {
        "roe_median":  18.0, "roe_range": ( 12.2,  30.2),
        "pat_median":   4.3, "pat_range": (-35.4,   9.8),
        "pe_median":   36.5, "pe_range":  ( 34.8,  46.0),
    },
    "Textiles": {
        "roe_median":  11.3, "roe_range": (  8.8,  14.5),
        "pat_median":   5.9, "pat_range": (  2.4,   8.1),
        "pe_median":   32.7, "pe_range":  ( 27.9,  37.6),
    },
}