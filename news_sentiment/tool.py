# =============================================================================
# news_sentiment/tool.py
# =============================================================================

import json
import logging
from typing import List
from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool
def run_news_sentiment(symbols: List[str]) -> str:
    """
    Fetches and scores news sentiment for a list of NSE stock symbols.

    Call this tool for ALL trade types (medium, short, swing).
    Always called LAST — after technical (and fundamental for medium)
    have identified the shortlist.

    Do NOT slice or limit the symbols list — pass every symbol TA approved.

    Args:
        symbols: List of NSE tickers WITHOUT .NS suffix.
                 Example: '["RELIANCE", "TCS", "INFY"]'

    Returns:
        JSON string — one record per symbol:
          matched_symbol  : NSE ticker
          weighted_score  : float -1.0 to +1.0
          signal_strength : "STRONG POSITIVE" | "POSITIVE" | "NEUTRAL" |
                            "NEGATIVE" | "STRONG NEGATIVE" | "NO_NEWS"
          dominant_label  : "positive" | "negative" | "neutral"
          g_confidence    : float 0.0-1.0
          article_count   : int
          sources         : comma-separated source names
    """
    try:
        if not isinstance(symbols, list):
            return json.dumps({"error": "symbols must be a list of ticker strings."})

        logger.info(f"News tool: analysing {len(symbols)} symbols...")

        from news_sentiment.main import run as news_run
        all_records = news_run()

        # Filter to requested symbols only
        filtered = [
            r for r in all_records
            if r.get("matched_symbol") in symbols
        ]

        # Add NO_NEWS placeholder for any symbol not covered
        covered = {r["matched_symbol"] for r in filtered}
        for sym in symbols:
            if sym not in covered:
                filtered.append({
                    "matched_symbol":  sym,
                    "weighted_score":  0.0,
                    "signal_strength": "NO_NEWS",
                    "dominant_label":  "neutral",
                    "g_confidence":    0.0,
                    "article_count":   0,
                    "sources":         "",
                })

        logger.info(f"News tool: returning {len(filtered)} records.")
        return json.dumps(filtered, indent=2, default=str)

    except Exception as e:
        logger.error(f"News sentiment tool failed: {e}")
        return json.dumps({"error": str(e)})