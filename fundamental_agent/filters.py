# ============================================================
# filters.py — Hard Disqualification Logic
# ============================================================

import logging
from typing import Dict, Any, Tuple

from fundamental_agent import config as cfg

logger = logging.getLogger(__name__)

def passes_hard_filters(data: Dict[str, Any]) -> Tuple[bool, str]:
    ticker = data.get("ticker", "UNKNOWN")
    sector = data.get("sector", "Unknown")
    is_asset_heavy = sector in cfg.ASSET_HEAVY_SECTORS

    logger.info(f"[{ticker}] Running strict hard filters (Sector: {sector})...")

    # 1. Debt to Equity Disqualification
    if not is_asset_heavy:
        de = data.get("debt_to_equity")
        max_de = cfg.HARD_FILTERS.get("max_debt_equity", 5.0)
        if de is not None and de > max_de:
            msg = f"Failed: D/E of {de:.2f} exceeds strict limit of {max_de}."
            logger.warning(f"[{ticker}] {msg}")
            return False, msg
            
    # 2. Return on Equity (Negative ROE Trap)
    roe = data.get("roe")
    eps_growth = data.get("eps_growth_1yr")
    profit_cagr = data.get("profit_cagr_3yr")
    
    # Strictly negative ROE means shareholder equity is being destroyed
    if roe is not None and roe < 0:
        msg = f"Failed: Negative ROE ({roe:.2f}%). Destroying shareholder value."
        logger.warning(f"[{ticker}] {msg}")
        return False, msg

    # THE "NONE" LOOPHOLE FIX (Catches IDEA)
    # Bankrupt companies often return 'None' for ROE. We check earnings to verify.
    if roe is None:
        if (eps_growth is not None and eps_growth < 0) or (profit_cagr is not None and profit_cagr < 0):
            msg = "Failed: Missing ROE combined with negative earnings growth (Zombie Risk)."
            logger.warning(f"[{ticker}] {msg}")
            return False, msg

    # 3. Earnings Collapse Filter
    if eps_growth is not None and eps_growth < -50.0 and (profit_cagr is None or profit_cagr < 0):
        msg = f"Failed: Catastrophic 1-Yr EPS decline ({eps_growth:.2f}%)."
        logger.warning(f"[{ticker}] {msg}")
        return False, msg

    logger.info(f"[{ticker}] Passed strict hard filters.")
    return True, "Passed"