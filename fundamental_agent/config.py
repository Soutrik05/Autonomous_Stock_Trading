# ============================================================
# config.py — Fundamental Agent Configuration
# ============================================================

# ── Hard Disqualification Filters ──────────────────────────
HARD_FILTERS = {
    "max_debt_equity":           2.5,
    "min_negative_eps_quarters": 2,
    "min_roe":                   0.0,
}

# ── PE Reliability Thresholds ───────────────────────────────
# If implied PE > this → unreliable (currency mismatch / ultra-high-PE).
# PE excluded from scoring entirely; weight redistributed.
PE_UNRELIABLE_THRESHOLD = 200

# If our computed PE and yfinance's trailingPE diverge by > this % →
# use yfinance's trailingPE. Catches stocks where trailingPE is correct
# but the divergence check can help.
PE_DIVERGENCE_WARN_PCT = 40

# PE below this value is treated as unreliable — same as PE > 500x.
# A Nifty 500 stock with PE < 1.0 is a data error, not a real value.
# (TATASTEEL: EPS=632 vs price=193 → both our PE and yf trailingPE = 0.3x.
# The sanity check discards info EPS but yf trailingPE is computed the same
# way, so it's also 0.3x. The floor check catches this final case.)
# Legitimate distressed PE (2–4x) is well above 1.0. Safe threshold.
PE_MIN_PLAUSIBLE = 1.0

# ── PE Sanity Check ─────────────────────────────────────────
# If info["epsTrailingTwelveMonths"] > current price, yfinance has
# returned total net income (wrong units), not per-share EPS.
# A per-share EPS can never exceed the stock price (that would imply
# PE < 1x, which is essentially impossible for a non-bankrupt company).
# When this triggers, we discard info EPS and fall back to trailingPE.
# This is the root cause of TATASTEEL showing PE = 0.3x.
PE_EPS_SANITY_CHECK = True   # set False only to debug

# ── Universal Scoring Bands ─────────────────────────────────
# Used when no sector benchmark is available.
# Each metric scored 0–100. Format: (threshold, score).

PE_SCORE_BANDS = [
    (10,          100),
    (15,           85),
    (20,           70),
    (25,           55),
    (30,           40),
    (40,           25),
    (float("inf"), 10),
]

PB_SCORE_BANDS = [
    (1.0,          100),
    (2.0,           85),
    (3.0,           70),
    (4.0,           55),
    (5.0,           35),
    (float("inf"),  15),
]

DE_SCORE_BANDS = [
    (0.25, 100),
    (0.5,   90),
    (0.75,  80),
    (1.0,   65),
    (1.5,   50),
    (2.0,   30),
    (2.5,   15),
]

EPS_GROWTH_SCORE_BANDS = [
    (30,            100),
    (20,             85),
    (10,             70),
    (5,              55),
    (0,              35),
    (-float("inf"),  10),
]

FCF_SCORE_BANDS = [
    (5000,          100),
    (1000,           85),
    (500,            70),
    (0,              50),
    (-500,           25),
    (-float("inf"),   5),
]

# Universal fallback bands for ROE and PAT margin (used when sector unknown)
ROE_SCORE_BANDS_UNIVERSAL = [
    (25,  100),
    (20,   85),
    (15,   70),
    (10,   55),
    (5,    35),
    (0,    15),
]

PAT_MARGIN_SCORE_BANDS_UNIVERSAL = [
    (25,  100),
    (20,   85),
    (15,   70),
    (10,   55),
    (5,    35),
    (0,    15),
    (-float("inf"), 0),
]

# ── Sector Benchmarks ────────────────────────────────────────
# Used for sector-relative scoring of ROE, PAT margin, and PE.
# Keys match yfinance's info["sector"] strings exactly.
#
# Each entry:
#   roe_median:  typical ROE % for profitable companies in this sector
#   roe_range:   (low, high) — full normal range. Above high = exceptional.
#   pat_median:  typical PAT margin %
#   pat_range:   (low, high)
#   pe_median:   typical trailing PE
#   pe_range:    (low, high)
#
# Sources: NSE data, Screener.in sector pages, annual reports FY23-25.
# These are Indian market benchmarks, NOT US GICS benchmarks.
#
# Sector strings that yfinance uses for NSE stocks:
#   Technology, Financial Services, Energy, Basic Materials,
#   Industrials, Consumer Defensive, Consumer Cyclical,
#   Healthcare, Utilities, Communication Services, Real Estate
#
# Known yfinance misclassifications (documented, not fixed here):
#   RELIANCE → "Energy"  (actually conglomerate; retail+telecom+refining)
#   ITC      → "Consumer Defensive"  (tobacco+FMCG+hotels)
#   Apollo Hospitals → "Healthcare"  (hospitals ≠ pharma, different margins)
#   HDFC Life → "Financial Services" (insurance ≠ bank, different ROE profile)

SECTOR_BENCHMARKS = {
    "Technology": {
        # IT services: TCS, Infy, Wipro, HCL, LTIM — high ROE, strong margins
        "roe_median": 30, "roe_range": (20, 50),
        "pat_median": 22, "pat_range": (15, 35),
        "pe_median":  25, "pe_range":  (18, 35),
    },
    "Financial Services": {
        # Banks, NBFCs, insurance — moderate ROE, high PAT margin (on NII basis)
        # Banks structurally run 12-18% ROE; PAT margin looks high because revenue = NII
        "roe_median": 14, "roe_range": (10, 20),
        "pat_median": 22, "pat_range": (15, 30),
        "pe_median":  18, "pe_range":  (10, 28),
    },
    "Energy": {
        # Oil & gas (ONGC, BPCL, IOC), refiners — low PAT margins, moderate ROE
        # COALINDIA outlier: PAT margin ~23% (royalty model, not capital-intensive)
        "roe_median": 12, "roe_range": (8,  18),
        "pat_median":  7, "pat_range": (4,  15),
        "pe_median":  10, "pe_range":  (6,  18),
    },
    "Basic Materials": {
        # Metals (TATASTEEL, JSW, Hindalco), chemicals, cement
        # Cyclical — earnings volatile, margins thin in metals
        "roe_median": 12, "roe_range": (6,  20),
        "pat_median":  8, "pat_range": (3,  15),
        "pe_median":  12, "pe_range":  (6,  22),
    },
    "Industrials": {
        # Defence PSUs (HAL, BEL, GRSE), capital goods, engineering
        # High ROE possible for asset-light defence contractors
        "roe_median": 18, "roe_range": (10, 30),
        "pat_median": 10, "pat_range": (5,  22),
        "pe_median":  28, "pe_range":  (18, 50),
    },
    "Consumer Defensive": {
        # FMCG (HUL, Nestle, Britannia), tobacco (ITC)
        # Typically high ROE and margins, premium PE
        "roe_median": 28, "roe_range": (18, 55),
        "pat_median": 15, "pat_range": (8,  25),
        "pe_median":  40, "pe_range":  (25, 60),
    },
    "Consumer Cyclical": {
        # Auto (Maruti, M&M, Bajaj), retail, hospitality
        "roe_median": 18, "roe_range": (10, 30),
        "pat_median": 10, "pat_range": (5,  18),
        "pe_median":  28, "pe_range":  (15, 45),
    },
    "Healthcare": {
        # Pharma (Sun, Cipla, Divi's) AND hospitals (Apollo, Fortis)
        # Note: hospitals have lower margins than pharma; yfinance lumps them together
        "roe_median": 18, "roe_range": (10, 30),
        "pat_median": 14, "pat_range": (8,  25),
        "pe_median":  28, "pe_range":  (18, 45),
    },
    "Utilities": {
        # Power generation/transmission (NTPC, POWERGRID, Adani Green)
        # Capital intensive, regulated returns — low ROE but high PAT margins
        # (PAT margin high because revenue is small relative to asset base)
        "roe_median": 13, "roe_range": (8,  20),
        "pat_median": 28, "pat_range": (18, 42),
        "pe_median":  18, "pe_range":  (12, 30),
    },
    "Communication Services": {
        # Telecom (Bharti, Indus Towers), media
        "roe_median": 12, "roe_range": (6,  20),
        "pat_median": 14, "pat_range": (5,  25),
        "pe_median":  22, "pe_range":  (12, 35),
    },
    "Real Estate": {
        # Developers (DLF, Godrej Properties), REITs
        "roe_median": 12, "roe_range": (6,  22),
        "pat_median": 18, "pat_range": (8,  35),
        "pe_median":  30, "pe_range":  (15, 55),
    },
}

# ── Metric Weights ──────────────────────────────────────────
# Must sum to 1.0.
# ROE and PAT margin are now sector-relative scored.
# Revenue growth removed (correlated with EPS growth; EPS more informative).
METRIC_WEIGHTS = {
    "pe":         0.15,
    "pb":         0.10,
    "roe":        0.20,
    "de":         0.15,
    "pat_margin": 0.15,
    "eps_growth": 0.20,
    "fcf":        0.05,
}

assert abs(sum(METRIC_WEIGHTS.values()) - 1.0) < 1e-6, "Metric weights must sum to 1.0"

PE_FALLBACK_WEIGHT_REDISTRIBUTION = {
    "pb":         0.05,
    "roe":        0.05,
    "eps_growth": 0.05,
}

assert abs(sum(PE_FALLBACK_WEIGHT_REDISTRIBUTION.values()) - METRIC_WEIGHTS["pe"]) < 1e-6, \
    "PE fallback redistribution must sum to PE's original weight (0.15)"

# ── Data Settings ───────────────────────────────────────────
NSE_SUFFIX                = ".NS"
QUARTERLY_HISTORY_PERIODS = 4

# Max ratio of TTM EPS to prior year EPS before flagging a unit mismatch.
# yfinance annual stmt sometimes returns EPS in USD (from ADR filings) while
# trailingEps is in INR — producing ~84x mismatch (62 INR / 0.66 USD = 93x).
# Legitimate turnaround companies can grow EPS 10-20x in extreme cases.
# 20x threshold catches all currency mismatches while allowing real recoveries.
EPS_GROWTH_MAX_RATIO = 20.0

# ── Score Settings ──────────────────────────────────────────
SCORE_UNAVAILABLE_PENALTY = 20

# ── Orchestrator Output Settings ────────────────────────────
# Only stocks scoring above this threshold (0–1) are sent to orchestrator.
# Stocks below this are considered too weak to be worth the orchestrator's
# attention regardless of how many are in the universe.
ORCHESTRATOR_MIN_SCORE = 0.60
 
# Output directory for timestamped JSON files.
# Each run produces: fundamental_YYYYMMDD_HHMMSS.json
ORCHESTRATOR_OUTPUT_DIR = "results/fundamental_runs"
