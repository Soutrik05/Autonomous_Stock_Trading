import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Path to the root-level data folder
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
NIFTY_CSV = os.path.join(DATA_DIR, "nifty500_constituents.csv")

_SECTOR_MAP_CACHE = None
_NIFTY_TICKER_CACHE = None

def load_nifty500_tickers() -> list:
    """Loads and caches the ticker list for the Orchestrator."""
    global _NIFTY_TICKER_CACHE
    if _NIFTY_TICKER_CACHE is None:
        df = pd.read_csv(NIFTY_CSV)
        _NIFTY_TICKER_CACHE = df["Symbol"].dropna().str.strip().str.upper().tolist()
    return _NIFTY_TICKER_CACHE

def get_sector_map() -> dict:
    """Loads and caches the sector mapping for all Agents to use."""
    global _SECTOR_MAP_CACHE
    if _SECTOR_MAP_CACHE is None:
        df = pd.read_csv(NIFTY_CSV)
        _SECTOR_MAP_CACHE = dict(zip(df["Symbol"], df["Industry"]))
    return _SECTOR_MAP_CACHE