# ============================================================
# screener_fetcher.py — Screener.in Data Retrieval & Caching
# ============================================================

import os
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fundamental_agent import config as cfg

import threading
import random

logger = logging.getLogger(__name__)

# Semaphore that allows a MAXIMUM of 3 concurrent live network requests.
_NETWORK_SEMAPHORE = threading.Semaphore(3)

# Lock for safe File I/O
_CACHE_LOCK = threading.Lock()

def _polite_delay():
    """Adds a random delay between 1.5 and 3.5 seconds to mimic human browsing."""
    time.sleep(random.uniform(1.5, 3.5))


# Fake headers to prevent 403 Forbidden errors from Screener
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── Caching Logic ───────────────────────────────────────────

# Dynamically find the fundamental_agent/cache/ folder no matter where the script is run
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = os.path.join(_CURRENT_DIR, "..", "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
SCREENER_CACHE_PATH = os.path.join(_CACHE_DIR, "screener_cache.json")

def _load_cache() -> Dict[str, Any]:
    """Loads the Screener cache from disk."""
    if not os.path.exists(SCREENER_CACHE_PATH):
        return {}
    try:
        with open(SCREENER_CACHE_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load Screener cache. Starting fresh. Error: {e}")
        return {}

def _save_cache(cache_data: Dict[str, Any]):
    """Saves the Screener cache to disk."""
    try:
        with open(SCREENER_CACHE_PATH, "w") as f:
            json.dump(cache_data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save Screener cache: {e}")

def _is_cache_valid(timestamp_str: str) -> bool:
    """Checks if the cached data is still within the TTL window."""
    try:
        cached_time = datetime.fromisoformat(timestamp_str)
        expiration_time = cached_time + timedelta(hours=cfg.SCREENER_CACHE_TTL_HOURS)
        return datetime.now() < expiration_time
    except Exception:
        return False


# ── Scraping & Parsing Logic ────────────────────────────────

def _extract_top_ratio(soup: BeautifulSoup, metric_name: str) -> Optional[float]:
    """
    Extracts a value from the 'top-ratios' grid at the top of a Screener page.
    """
    try:
        spans = soup.find_all('span', class_='name')
        for span in spans:
            if metric_name.lower() in span.text.lower():
                value_span = span.find_next_sibling('span', class_='nowrap')
                if value_span:
                    num_span = value_span.find('span', class_='number')
                    if num_span:
                        # Remove commas (e.g., "1,234.50" -> "1234.50")
                        return float(num_span.text.replace(',', ''))
    except Exception as e:
        logger.debug(f"Failed to extract {metric_name} from top ratios: {e}")
    return None

def _extract_table_row_latest(soup: BeautifulSoup, section_id: str, row_name: str) -> Optional[float]:
    """
    Extracts the latest year's value from a specific financial table row.
    Used as a fallback for metrics not in the top ratio grid.
    """
    try:
        section = soup.find('section', id=section_id)
        if not section:
            return None
        
        rows = section.find_all('tr')
        for row in rows:
            tds = row.find_all('td')
            if tds and row_name.lower() in tds[0].text.lower():
                # The last <td> in the row is usually the TTM or latest year
                latest_val_text = tds[-1].text.strip().replace(',', '')
                if latest_val_text and latest_val_text != '':
                    return float(latest_val_text)
    except Exception as e:
        logger.debug(f"Failed to extract {row_name} from {section_id} table: {e}")
    return None

def _parse_screener_html(html: str) -> Dict[str, Any]:
    """Parses the raw HTML to extract exact fundamental values."""
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        "roce": None,
        "roe": None,
        "debt_to_equity": None,
        "fcf_crores": None,
        "pe_ratio": None, # Used to cross-check yfinance
        "market_cap_crores": None
    }

    # 1. Easy Extractions (Top Ratios Grid)
    data["roce"] = _extract_top_ratio(soup, "ROCE")
    data["roe"] = _extract_top_ratio(soup, "ROE")
    data["pe_ratio"] = _extract_top_ratio(soup, "Stock P/E")
    
    # ── Extract Market Cap ──
    data["market_cap_crores"] = _extract_top_ratio(soup, "Market Cap")

    data["total_assets"] = _extract_top_ratio(soup, "Total Assets")
    data["profit_after_tax"] = _extract_top_ratio(soup, "Profit after tax")

    # Debt to Equity is sometimes in the top grid, sometimes not.
    data["debt_to_equity"] = _extract_top_ratio(soup, "Debt to equity")

    # 2. Hard Extractions (Table Parsing Fallbacks)
    
    # Fallback: Calculate D/E from Balance Sheet if missing from top grid
    if data["debt_to_equity"] is None:
        borrowings = _extract_table_row_latest(soup, "balance-sheet", "Borrowings")
        share_capital = _extract_table_row_latest(soup, "balance-sheet", "Share Capital")
        reserves = _extract_table_row_latest(soup, "balance-sheet", "Reserves")
        
        if borrowings is not None and share_capital is not None and reserves is not None:
            total_equity = share_capital + reserves
            if total_equity > 0:
                data["debt_to_equity"] = round(borrowings / total_equity, 2)

    # Calculate Free Cash Flow (FCF) = Cash from Operating Activity - CapEx
    cfo = _extract_table_row_latest(soup, "cash-flow", "Cash from Operating Activity")
    # CapEx is usually listed as 'Fixed assets purchased' under Investing Activity
    capex = _extract_table_row_latest(soup, "cash-flow", "Fixed assets purchased")
    
    if cfo is not None:
        # CapEx is usually a negative number in the table, so we add it. 
        # If it's recorded as positive, we subtract it.
        capex_val = capex if capex is not None else 0
        if capex_val > 0:
            capex_val = -capex_val 
            
        data["fcf_crores"] = cfo + capex_val

    # ── Smart Money Extraction ──
    data["promoter_holding"] = None
    data["fii_change"] = None
    data["promoter_change"] = None

    try:
        share_section = soup.find('section', id='shareholding')
        if share_section:
            rows = share_section.find_all('tr')
            for row in rows:
                tds = row.find_all('td')
                if len(tds) > 1:
                    label = tds[0].text.strip()
                    try:
                        latest_val = float(tds[-1].text.strip().replace('%', ''))
                        prev_val = float(tds[-2].text.strip().replace('%', ''))
                        
                        if "Promoters" in label:
                            data["promoter_holding"] = latest_val
                            data["promoter_change"] = round(latest_val - prev_val, 2)
                        elif "FIIs" in label:
                            data["fii_change"] = round(latest_val - prev_val, 2)
                    except ValueError:
                        continue
    except Exception as e:
        logger.debug(f"Failed to parse smart money: {e}")

    return data


# ── Main Orchestrator ───────────────────────────────────────

def fetch_screener_data(ticker: str) -> Dict[str, Any]:
    """
    Fetches fundamental data from Screener.in for a given ticker.
    Utilizes thread-safe caching to prevent bans and speed up execution.
    """
    
    # 1. Thread-Safe Cache Read
    with _CACHE_LOCK:
        cache = _load_cache()
    
    # 2. Check Cache
    if ticker in cache and _is_cache_valid(cache[ticker].get("timestamp", "")):
        return cache[ticker]["data"]
            
    # 3. CACHE MISS: Fetch fresh data politely
    with _NETWORK_SEMAPHORE:
        
        # DOUBLE-CHECK: Did another thread fetch this while we were waiting for the semaphore?
        with _CACHE_LOCK:
            cache = _load_cache()
            if ticker in cache and _is_cache_valid(cache[ticker].get("timestamp", "")):
                return cache[ticker]["data"]
                
        logger.info(f"Cache miss for {ticker}: Fetching fresh Screener data politely...")
        _polite_delay()

        urls_to_try = [
            f"https://www.screener.in/company/{ticker}/consolidated/",
            f"https://www.screener.in/company/{ticker}/"
        ]

        html_content = None

        for url in urls_to_try:
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                if response.status_code == 200:
                    if "company-profile" in response.text or "top-ratios" in response.text:
                        html_content = response.text
                        break 
            except Exception as e:
                logger.error(f"Failed to fetch {ticker}: {e}")
                return {}
                
            time.sleep(1) # Polite delay between fallback attempts

        # 4. Parse and Thread-Safe Save
        if html_content:
            parsed_data = _parse_screener_html(html_content)
            
            # Lock the file while we update and save it!
            with _CACHE_LOCK:
                # Reload cache one last time just to be safe before overwriting
                latest_cache = _load_cache()
                latest_cache[ticker] = {
                    "timestamp": datetime.now().isoformat(),
                    "data": parsed_data
                }
                _save_cache(latest_cache)
                
            return parsed_data
        else:
            logger.error(f"Failed to retrieve valid Screener HTML for {ticker}.")
            return {
                "roce": None,
                "roe": None,
                "debt_to_equity": None,
                "fcf_crores": None,
                "pe_ratio": None,
                "market_cap_crores": None,
                "total_assets": None,
                "profit_after_tax": None
            }