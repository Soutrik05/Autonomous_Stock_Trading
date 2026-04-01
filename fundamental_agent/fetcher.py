# ============================================================
# fundamental_agent/fetcher.py
#
# All yfinance data fetching and raw metric computation.
# Nothing in this file scores, filters, or makes decisions —
# it only fetches and computes raw values from market data.
#
# Single public function: fetch_stock_data(ticker_nse) -> dict
# Called once per stock by tool.py.
#
# Design notes carried forward from original agent.py:
#   - Statements (income + balance sheet) are fetched ONCE per
#     stock and reused across all downstream computations.
#     This avoids redundant yfinance calls which are slow.
#   - ROE always from statements (never info["returnOnEquity"]).
#   - D/E always from balance sheet (info["debtToEquity"] is wrong).
#   - EPS growth from TTM trailingEps vs annual stmt prior year.
#     info["earningsGrowth"] is single-quarter YoY, not annual.
#   - FCF components (Op CF + CapEx) exposed separately so the
#     LLM layer can reason about FCF quality, not just the sign.
# ============================================================

import logging
from typing import Any, Dict, Optional, Tuple

import yfinance as yf

from fundamental_agent import config as cfg

logger = logging.getLogger("fundamental_agent.fetcher")


# ============================================================
# SECTION 1 — DataFrame Helpers
# ============================================================

def _get_row(df, labels: list) -> Optional[object]:
    """
    Finds the first matching row in a yfinance DataFrame by label.
    Drops NaN values before returning so callers get clean data.
    Returns None if no label matches or the matched row is empty.
    """
    for label in labels:
        if label in df.index:
            row = df.loc[label].dropna()
            if not row.empty:
                return row
    return None


def _first_val(df, labels: list) -> Optional[float]:
    """
    Returns the first non-NaN value from the first matching row.
    Convenience wrapper over _get_row for scalar lookups.
    """
    row = _get_row(df, labels)
    return float(row.iloc[0]) if row is not None else None


# ============================================================
# SECTION 2 — Statement-Derived Computations
# ============================================================

def _compute_de(bs) -> Optional[float]:
    """
    Computes D/E ratio from the quarterly balance sheet.

    Why not info["debtToEquity"]:
        yfinance's debtToEquity is inconsistently scaled across stocks —
        sometimes it's a ratio (0.5), sometimes percentage (50.0).
        We compute it directly from balance sheet rows to be consistent.

    Returns the ratio as a decimal (e.g. 0.75 means D/E = 0.75x).
    Returns None if debt or equity data is unavailable.
    Returns 0.0 if debt is explicitly zero.
    """
    total_debt = _first_val(bs, [
        "Total Debt",
        "Long Term Debt And Capital Lease Obligation",
        "Long Term Debt",
        "Short Long Term Debt",
    ])
    equity = _first_val(bs, [
        "Stockholders Equity",
        "Total Equity Gross Minority Interest",
        "Common Stock Equity",
    ])
    if total_debt is None:          return None
    if total_debt == 0:             return 0.0
    if not equity or equity <= 0:   return None
    return round(total_debt / equity, 4)


def _compute_roe(inc, bs) -> Optional[float]:
    """
    Computes TTM ROE as: TTM Net Income / Average Shareholders Equity.
    Returns a decimal (e.g. 0.185 means ROE = 18.5%).

    TTM Net Income = sum of the 4 most recent quarterly net income rows.
    Average Equity = mean of the 2 most recent quarterly equity snapshots.

    Why 4 quarters of net income:
        We want a full trailing 12-month picture, not a single quarter
        annualised. Summing 4 quarters handles seasonality properly.

    Why average equity (not just current):
        Equity grows as profits are retained. Using only the ending equity
        overstates ROE slightly. The average of start and end is standard
        practice (also how DuPont analysis is taught in Varsity Module 3).
    """
    ni_row = _get_row(inc, ["Net Income", "Net Income Common Stockholders"])
    if ni_row is None or len(ni_row) < 4:
        return None

    eq_row = _get_row(bs, [
        "Stockholders Equity",
        "Total Equity Gross Minority Interest",
        "Common Stock Equity",
    ])
    if eq_row is None:
        return None

    ttm_ni = float(ni_row.iloc[:4].sum())
    avg_eq = (
        float(eq_row.iloc[:2].mean()) if len(eq_row) >= 2
        else float(eq_row.iloc[0])
    )
    if avg_eq <= 0:
        return None
    return ttm_ni / avg_eq


def _compute_negative_eps_quarters(inc) -> int:
    """
    Counts the number of *consecutive* negative EPS quarters
    starting from the most recent quarter.

    Stops counting at the first positive quarter — we care about
    a current losing streak, not isolated past losses.

    Falls back to net income rows if EPS rows are unavailable.
    """
    eps_row = _get_row(inc, ["Diluted EPS", "Basic EPS"])
    if eps_row is None:
        eps_row = _get_row(inc, ["Net Income", "Net Income Common Stockholders"])
    if eps_row is None:
        return 0

    count = 0
    for val in eps_row.iloc[:cfg.QUARTERLY_HISTORY_PERIODS]:
        if float(val) < 0:
            count += 1
        else:
            break   # streak broken — stop
    return count


def _compute_ttm_eps_from_stmt(inc) -> Optional[float]:
    """
    Computes TTM EPS by summing the 4 most recent quarterly EPS values.
    Used only as an internal cross-check, not as the primary EPS source.

    Primary EPS source for growth calculation is info["trailingEps"]
    because yfinance's trailingEps is in INR and has near-100% coverage.
    """
    eps_row = _get_row(inc, ["Diluted EPS", "Basic EPS"])
    if eps_row is not None and len(eps_row) >= 4:
        return float(eps_row.iloc[:4].sum())

    # Fallback: compute from NI / shares
    ni_row = _get_row(inc, ["Net Income", "Net Income Common Stockholders"])
    sh_row = _get_row(inc, ["Diluted Average Shares", "Basic Average Shares"])
    if ni_row is None or sh_row is None or len(ni_row) < 4:
        return None

    q = min(len(ni_row), len(sh_row), 4)
    s = sum(
        float(ni_row.iloc[i]) / float(sh_row.iloc[i])
        for i in range(q) if float(sh_row.iloc[i]) != 0
    )
    return s if q == 4 else None


# ============================================================
# SECTION 3 — PE Resolution (three-stage check)
# ============================================================

def _resolve_pe(
    current_price:  Optional[float],
    ttm_eps_info:   Optional[float],
    yf_trailing_pe: Optional[float],
    ticker_nse:     str,
) -> Tuple[Optional[float], bool, bool]:
    """
    Resolves the final PE value through three validation stages.

    Stage 0 — EPS sanity check:
        EPS can never exceed the stock price for a non-bankrupt company
        (that would imply PE < 1x). If info EPS > current price, yfinance
        has returned total net income in wrong units (not per-share).
        Root cause of TATASTEEL showing PE=0.3x (EPS=632, price=193).
        Fix: discard info EPS, fall through to yf_trailing_pe.

    Stage 1 — Divergence check:
        If our computed PE and yf trailingPE differ by >40%, use yf's
        value. Less necessary after Stage 0 but kept as a safety net
        for other edge cases.

    Stage 2 — Plausibility bounds:
        PE > PE_UNRELIABLE_THRESHOLD (200x): too high to be meaningful,
        flag as unreliable and exclude from scoring.
        PE < PE_MIN_PLAUSIBLE (1.0x): data error, flag as unreliable.

    Returns:
        (pe_value, pe_divergence_flag, pe_unreliable_flag)
        pe_value is None if unreliable (scoring will redistribute weight).
    """
    if not current_price or current_price <= 0:
        if yf_trailing_pe and yf_trailing_pe > 0:
            unrel = yf_trailing_pe > cfg.PE_UNRELIABLE_THRESHOLD
            return (None if unrel else round(yf_trailing_pe, 2)), False, unrel
        return None, False, False

    # Stage 0: EPS sanity — per-share EPS cannot exceed stock price
    eps_to_use = ttm_eps_info
    if (
        cfg.PE_EPS_SANITY_CHECK
        and ttm_eps_info is not None
        and ttm_eps_info > current_price
    ):
        logger.warning(
            f"{ticker_nse}: EPS sanity fail — "
            f"info EPS ({ttm_eps_info:.2f}) > price ({current_price:.2f}). "
            f"yfinance returned total income, not per-share. "
            f"Discarding info EPS, using trailingPE directly."
        )
        eps_to_use = None

    # Stage 1: compute our PE and check divergence from yf
    our_pe        = (current_price / eps_to_use) if (eps_to_use and eps_to_use > 0) else None
    pe_divergence = False
    final_pe      = our_pe

    if our_pe is not None and yf_trailing_pe and yf_trailing_pe > 0:
        div_pct = abs(our_pe - yf_trailing_pe) / yf_trailing_pe * 100
        if div_pct > cfg.PE_DIVERGENCE_WARN_PCT:
            pe_divergence = True
            final_pe      = yf_trailing_pe
            logger.warning(
                f"{ticker_nse}: PE divergence — "
                f"our={our_pe:.1f}x  yf={yf_trailing_pe:.1f}x  "
                f"diff={div_pct:.0f}% → using yf value"
            )
    elif our_pe is None and yf_trailing_pe and yf_trailing_pe > 0:
        final_pe = yf_trailing_pe

    # Stage 2: plausibility bounds
    if final_pe is not None and final_pe > cfg.PE_UNRELIABLE_THRESHOLD:
        logger.warning(f"{ticker_nse}: PE={final_pe:.0f}x > threshold → unreliable")
        return None, pe_divergence, True

    if final_pe is not None and final_pe < cfg.PE_MIN_PLAUSIBLE:
        logger.warning(
            f"{ticker_nse}: PE={final_pe:.2f}x < min plausible {cfg.PE_MIN_PLAUSIBLE}x "
            f"→ data error, flagging unreliable"
        )
        return None, pe_divergence, True

    if final_pe is not None and final_pe <= 0:
        return None, pe_divergence, False

    return (round(final_pe, 2) if final_pe else None), pe_divergence, False


# ============================================================
# SECTION 4 — EPS Growth
# ============================================================

def _get_eps_growth(
    info:  dict,
    stock: yf.Ticker,
) -> Tuple[Optional[float], str]:
    """
    Computes annual YoY EPS growth as:
        (TTM EPS − Prior full fiscal year EPS) / |Prior year EPS| × 100

    Why info["earningsGrowth"] is NOT used:
        info["earningsGrowth"] = single-quarter YoY, not full-year.
        RELIANCE showed 0.6% from this field; actual annual is 19.4%.

    Data sources:
        TTM EPS:   info["trailingEps"] — per-share INR, ~99% coverage.
        Prior EPS: annual_income_stmt["Diluted EPS"].iloc[0] — most
                   recent complete fiscal year EPS.

    Unit mismatch guard:
        yfinance sometimes returns annual stmt EPS in USD (ADR filing)
        while trailingEps is in INR, creating a ~84x ratio.
        If ttm_eps / prior_eps > EPS_GROWTH_MAX_RATIO (20x) and prior
        is positive, we skip the calculation rather than return garbage.
        Negative prior (loss-to-profit recovery) is always passed through.

    Returns:
        (eps_growth_pct, source_label)
        source_label is "annual" on success, "none" on any failure.
    """
    ttm_eps = info.get("trailingEps") or info.get("epsTrailingTwelveMonths")
    if ttm_eps is None or ttm_eps <= 0:
        return None, "none"

    try:
        annual = stock.income_stmt
        if annual is None or annual.empty:
            return None, "none"

        prior_eps_row = _get_row(annual, ["Diluted EPS", "Basic EPS"])
        if prior_eps_row is None or len(prior_eps_row) < 1:
            return None, "none"

        prior_eps = float(prior_eps_row.iloc[0])
        if prior_eps == 0:
            return None, "none"

        # Unit mismatch guard (only applies when prior is positive)
        if prior_eps > 0 and (ttm_eps / prior_eps) > cfg.EPS_GROWTH_MAX_RATIO:
            logger.warning(
                f"EPS unit mismatch: ttm={ttm_eps:.2f} INR, "
                f"prior={prior_eps:.4f} (likely USD from annual stmt). "
                f"Ratio={ttm_eps / prior_eps:.0f}x > max {cfg.EPS_GROWTH_MAX_RATIO}x. "
                f"Skipping growth calculation."
            )
            return None, "none"

        growth = round(((ttm_eps - prior_eps) / abs(prior_eps)) * 100, 2)
        logger.debug(
            f"EPS growth: TTM={ttm_eps:.2f}  prior_annual={prior_eps:.2f}  "
            f"growth={growth:.1f}%"
        )
        return growth, "annual"

    except Exception as e:
        logger.debug(f"EPS growth computation error: {e}")
    return None, "none"


# ============================================================
# SECTION 5 — Free Cash Flow
# ============================================================

def _get_fcf(stock: yf.Ticker) -> Dict[str, Optional[float]]:
    """
    Fetches FCF and its components (Operating CF and CapEx) separately.

    Returns:
        {"fcf": float|None, "operating_cf": float|None, "capex": float|None}
        All values in raw INR units (not Crores).

    Why expose components separately:
        FCF = Operating CF + CapEx (CapEx is negative in yfinance).
        For some companies (e.g. Suzlon), large order-book working capital
        buildup is classified as an operating outflow rather than capex.
        This can make FCF appear positive when the company is actually cash-
        constrained. Surfacing Op CF and CapEx separately lets the LLM
        reason about FCF quality rather than blindly trusting the sign.

    Fetch order:
        1. ttm_cashflow (preferred — trailing 12 months)
        2. cashflow (annual — fallback if TTM not available)
    """
    result: Dict[str, Optional[float]] = {
        "fcf":          None,
        "operating_cf": None,
        "capex":        None,
    }
    try:
        cf = stock.ttm_cashflow
        if cf is None or cf.empty:
            cf = stock.cashflow
        if cf is None or cf.empty:
            return result

        op_cf = _first_val(cf, ["Operating Cash Flow", "Cash Flow From Operations"])
        capex = _first_val(cf, ["Capital Expenditure", "Capital Expenditures"])
        result["operating_cf"] = op_cf
        result["capex"]        = capex

        # Prefer a direct FCF row; fall back to computed FCF
        direct = _first_val(cf, ["Free Cash Flow", "FreeCashFlow"])
        if direct is not None:
            result["fcf"] = direct
        elif op_cf is not None and capex is not None:
            result["fcf"] = op_cf + capex   # capex is negative → correct subtraction

    except Exception as e:
        logger.debug(f"FCF fetch error: {e}")
    return result


# ============================================================
# SECTION 6 — Main Fetch Entry Point
# ============================================================

def fetch_stock_data(ticker_nse: str) -> Dict[str, Any]:
    """
    Fetches all raw fundamental data for a single NSE stock.

    Fetches statements once and passes them to all sub-functions
    to avoid redundant yfinance network calls.

    Args:
        ticker_nse: Full NSE ticker with suffix, e.g. "RELIANCE.NS"

    Returns:
        Dict of raw metrics. All values are unscored and unfiltered.
        fetch_error is set to a string on failure, None on success.
        The caller (tool.py) is responsible for filtering and scoring.
    """
    result: Dict[str, Any] = {
        "ticker":               ticker_nse,
        "sector":               None,
        "industry":             None,
        "current_price":        None,
        "pe":                   None,
        "pe_divergence":        False,
        "pe_unreliable":        False,
        "pb":                   None,
        "roe":                  None,
        "de":                   None,
        "pat_margin":           None,
        "eps_growth_pct":       None,
        "eps_growth_source":    None,
        "fcf":                  None,
        "operating_cf":         None,
        "capex":                None,
        "negative_eps_quarters": 0,
        "fetch_error":          None,
    }

    try:
        stock = yf.Ticker(ticker_nse)
        info  = stock.info

        if not info or info.get("quoteType") is None:
            result["fetch_error"] = "Empty info — delisted or invalid ticker"
            return result

        # ── Fetch statements once ────────────────────────────
        inc, bs = None, None
        try:
            inc = stock.quarterly_income_stmt
        except Exception as e:
            logger.warning(f"{ticker_nse}: income stmt fetch failed — {e}")
        try:
            bs = stock.quarterly_balance_sheet
        except Exception as e:
            logger.warning(f"{ticker_nse}: balance sheet fetch failed — {e}")

        inc_ok = inc is not None and not inc.empty
        bs_ok  = bs  is not None and not bs.empty

        # ── Basic info ───────────────────────────────────────
        result["sector"]   = info.get("sector")
        result["industry"] = info.get("industry")

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        result["current_price"] = current_price

        # ── PE ───────────────────────────────────────────────
        pe_val, pe_div, pe_unrel = _resolve_pe(
            current_price  = current_price,
            ttm_eps_info   = info.get("epsTrailingTwelveMonths"),
            yf_trailing_pe = info.get("trailingPE"),
            ticker_nse     = ticker_nse,
        )
        result["pe"]            = pe_val
        result["pe_divergence"] = pe_div
        result["pe_unreliable"] = pe_unrel

        # ── P/B ──────────────────────────────────────────────
        result["pb"] = info.get("priceToBook")

        # ── PAT Margin ───────────────────────────────────────
        result["pat_margin"] = info.get("profitMargins")

        # ── D/E ──────────────────────────────────────────────
        if bs_ok:
            result["de"] = _compute_de(bs)
        # Fallback to info only if balance sheet computation failed
        if result["de"] is None:
            de_raw = info.get("debtToEquity")
            if de_raw is not None:
                # yfinance inconsistently returns ratio or percentage
                result["de"] = de_raw / 100 if de_raw > 10 else de_raw
                logger.debug(f"{ticker_nse}: D/E fallback from info: {result['de']:.4f}")

        # ── ROE ──────────────────────────────────────────────
        if inc_ok and bs_ok:
            result["roe"] = _compute_roe(inc, bs)

        # ── Negative EPS streak ──────────────────────────────
        if inc_ok:
            result["negative_eps_quarters"] = _compute_negative_eps_quarters(inc)

        # ── EPS Growth ───────────────────────────────────────
        eps_g, eps_src = _get_eps_growth(info, stock)
        result["eps_growth_pct"]    = eps_g
        result["eps_growth_source"] = eps_src

        # ── FCF + components ─────────────────────────────────
        fcf_data               = _get_fcf(stock)
        result["fcf"]          = fcf_data["fcf"]
        result["operating_cf"] = fcf_data["operating_cf"]
        result["capex"]        = fcf_data["capex"]

    except Exception as e:
        logger.error(f"{ticker_nse}: fatal fetch error — {e}")
        result["fetch_error"] = str(e)

    return result
