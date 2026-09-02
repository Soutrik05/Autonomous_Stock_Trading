# ============================================================
# fundamental_agent/fetcher/__init__.py
# ============================================================
import logging
from typing import Dict, Any

from fundamental_agent import config as cfg
from fundamental_agent.fetcher.yfinance_fetcher import fetch_yfinance_data
from fundamental_agent.fetcher.screener_fetcher import fetch_screener_data
from utils import get_sector_map

logger = logging.getLogger(__name__)

def _resolve_pe_ratio(y_pe: float, s_pe: float, ticker: str) -> float:
    """
    Resolves the PE ratio between YFinance and Screener.
    Implements the divergence sanity check from config.
    """
    if y_pe is None and s_pe is None:
        return None
    if y_pe is None:
        return s_pe
    if s_pe is None:
        return y_pe

    # Both exist, check for massive divergence (Accounting Noise Guard)
    max_pe = max(y_pe, s_pe)
    min_pe = min(y_pe, s_pe)
    
    if min_pe > 0:
        divergence_pct = ((max_pe - min_pe) / min_pe) * 100
        if divergence_pct > cfg.PE_DIVERGENCE_WARN_PCT:
            logger.warning(
                f"[{ticker}] High PE Divergence! YFinance: {y_pe:.2f}, Screener: {s_pe:.2f} "
                f"({divergence_pct:.1f}% diff). Defaulting to Screener (usually more accurate for NSE)."
            )
            
    # Screener is generally more reliable for Indian equities (TTM calculations)
    return s_pe

def fetch_all_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Orchestrates data fetching for a SINGLE ticker. 
    Uses YFinance for deep history/margins/debt.
    Uses Screener to overwrite key Valuation/Quality ratios.
    """
    
    try:
        y_data = fetch_yfinance_data(ticker)
        if not isinstance(y_data, dict): y_data = {}
            
        s_data = fetch_screener_data(ticker)
        if not isinstance(s_data, dict): s_data = {}
        
        # 1. Start with YFinance Baseline
        merged_data = {
            "ticker": ticker,
            "company_name": y_data.get("company_name", ticker),
            "sector": get_sector_map().get(ticker, "General"),
            "industry": y_data.get("industry", "Unknown"),
            "current_price": y_data.get("current_price", 0),
            "market_cap": y_data.get("market_cap", 0),
            
            "pb_ratio": y_data.get("pb_ratio"),
            "roe": y_data.get("roe"),
            "roce": y_data.get("roce"),
            "debt_to_equity": y_data.get("debt_to_equity"),
            
            "profit_cagr_3yr": y_data.get("profit_cagr_3yr"),
            "revenue_cagr_3yr": y_data.get("revenue_cagr_3yr"),
            "eps_growth_1yr": y_data.get("eps_growth_1yr"),

            "pat_margin": y_data.get("pat_margin"),
            "gross_margin": y_data.get("gross_margin"),
            "gpm": y_data.get("gpm"),
            "opm": y_data.get("opm"),
            "receivables_pct_sales": y_data.get("receivables_pct_sales"),
            
            "m_score_components": y_data.get("m_score_components", {"dsri": None, "gmi": None, "sgi": None, "lvgi": None, "tata": None}),
            
            "market_cap_crores": None,
            "fcf_crores": None 
        }

        # 2. RESOLVE PE RATIO EXPLICITLY
        merged_data["pe_ratio"] = _resolve_pe_ratio(y_data.get("pe_ratio"), s_data.get("pe_ratio"), ticker)

        # 3. OVERWRITE WITH SCREENER
        # Removed "pe_ratio" from this list so it doesn't overwrite our resolver logic
        metrics_to_overwrite = [
            "pb_ratio", "roe", "roce", 
            "fcf_crores", "market_cap_crores", 'debt_to_equity',
        ]
        
        for metric in metrics_to_overwrite:
            s_val = s_data.get(metric)
            if s_val is not None:
                merged_data[metric] = s_val

        return merged_data
        
    except Exception as e:
        logger.error(f"[{ticker}] Unexpected error during unified data merging: {e}")
        return {"ticker": ticker, "sector": "Unknown", "m_score_components": {}}