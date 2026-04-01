# =============================================================================
# agent.py
#
# LangChain @tool wrapper for the Technical Agent.
# This is the only file the Orchestrator interacts with.
#
# Orchestrates the full pipeline for every ticker:
#   1. Fetch OHLCV data (data_fetcher)
#   2. Compute all indicators (indicators/)
#   3. Extract signals (signal_extractor)
#   4. Score (scorer)
#   5. Return ranked JSON results
#
# The @tool decorator tells LangChain that the Orchestrator LLM
# can call this function autonomously when it needs technical analysis.
# =============================================================================

import logging
from typing import Optional, List
from langchain.tools import tool
import json

from technical_agent.data.data_fetcher import GrowwDataFetcher, load_nifty500_tickers, is_valid_df
from technical_agent.indicators.support_resistance import compute_support_resistance
from technical_agent.indicators.rsi import get_latest_rsi
from technical_agent.indicators.macd import compute_macd
from technical_agent.indicators.ema import compute_ema_crossover
from technical_agent.indicators.obv import compute_obv
from technical_agent.scoring.signal_extractor import extract_all_signals
from technical_agent.scoring.scorer import compute_score
from technical_agent.data.data_fetcher import get_market_regime
from technical_agent.scoring.scorer import apply_regime_filter

from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level fetcher instance
# Initialised once — avoids re-authenticating on every tool call.
# Set this up before the agent runs:
#   import technical_agent.agent as agent_module
#   agent_module._fetcher = GrowwDataFetcher(api_key=..., secret=...)
# ---------------------------------------------------------------------------
_fetcher: GrowwDataFetcher = None


def init_fetcher(api_key: str, secret: str) -> None:
    """
    Initialises the Groww data fetcher.
    Call this once at application startup before invoking the tool.
    """
    global _fetcher
    _fetcher = GrowwDataFetcher(api_key=api_key, secret=secret)
    logger.info("Technical Agent: fetcher initialised.")


# ---------------------------------------------------------------------------
# Core analysis function — separated from @tool for testability
# ---------------------------------------------------------------------------

def analyse_stocks(tickers: list, trade_type: str, top_n: int = 50, start_date = None) -> dict:
    """
    Runs the full technical analysis pipeline on a list of tickers.

    Args:
        tickers:    List of NSE ticker symbols.
        trade_type: "swing", "short", or "medium"
        top_n:      Return only the top N results by score.

    Returns:
        List of result dicts, sorted by score descending, capped at top_n.
    """
    if _fetcher is None:
        raise RuntimeError(
            "Fetcher not initialised. Call init_fetcher(api_key, secret) first."
        )
    
    # --- Market regime check ---
    regime = get_market_regime(end_date=start_date)

    results = []

    for ticker in tickers:
        try:
            # 1. Fetch data
            df = _fetcher.get_ohlcv(ticker, trade_type, end_date=start_date)

            # 2. Validate — skip if insufficient data
            if not is_valid_df(df, ticker, trade_type):
                continue

            # 3. Compute indicators
            rsi_value  = get_latest_rsi(df)
            macd_res   = compute_macd(df, trade_type)
            ema_res    = compute_ema_crossover(df, trade_type)
            obv_res    = compute_obv(df)
            sr_res     = compute_support_resistance(df)

            # 4. Extract signals
            signals = extract_all_signals(rsi_value, macd_res, ema_res, obv_res, sr_res)

            # 5. Score
            score_res = compute_score(signals, trade_type)

            # --- Apply regime filter ---
            score_res = apply_regime_filter(score_res, regime)

            results.append({
                "ticker":          ticker,
                "score":           score_res["score"],
                "label":           score_res["label"],
                "reasoning":       score_res["reasoning"],
                "signals":         score_res["signals"],
                "nearest_support":    sr_res["nearest_support"],
                "nearest_resistance": sr_res["nearest_resistance"],
                "support_strength":   sr_res["support_strength"],
                },
            )

        except Exception as e:
            # Never crash the entire run for one bad ticker
            logger.warning(f"{ticker}: analysis failed -- {e}")
            continue

    # Sort by score descending, return top N
    buy_stocks = [r for r in results if r["label"] in ("Buy", "Strong Buy","Watch")]
    buy_stocks.sort(key=lambda x: x["score"], reverse=True)
    return {
    "market_regime": regime,
    "total_scanned": len(results),
    "total_buy":     len(buy_stocks),
    "stocks":        buy_stocks,
    }


# ---------------------------------------------------------------------------
# LangChain @tool — entry point for the Orchestrator LLM
# ---------------------------------------------------------------------------

@tool
def run_technical_analysis(trade_type: str, tickers: Optional[List[str]] = None, top_n: int = 50) -> dict:
    """
    Runs technical analysis on all Nifty 500 stocks for the given trade type.

    Use this tool when you need to identify technically strong stocks for
    swing trades (2-10 days), short-term trades (2-8 weeks), or medium (3-6 months).
    The tool fetches live data, computes Support/Resistance levels, RSI, MACD, EMA crossovers, and
    OBV for each stock, then returns the top ranked opportunities as a dict.

    Args:
        trade_type: One of "swing", "short", or "medium"
        tickers:    Name of the stocks to run analysis on
        top_n:      Number of top stocks to return (default 50)
    
    For medium trades: pass the tickers list returned by run_fundamental_analysis.
    For swing/short trades: omit tickers — the tool scans the full Nifty 500.

    Returns:
        a dict with keys:
        market_regime:  current Nifty500 market condition
        total_scanned:  number of stocks analysed
        total_buy:      number of Buy/Strong/Watch Buy signals found
        stocks:         list of candidates sorted by score descending,
                        each with ticker, score, label, reasoning,
                        signals, nearest_support, nearest_resistance,
                        support strength
    """
    try:
        global _fetcher
        if _fetcher is None:
            from dotenv import load_dotenv
            import os
            load_dotenv()
            api_key = os.getenv("GROWW_API_KEY")
            secret  = os.getenv("GROWW_SECRET")
            if not api_key or not secret:
                return {"error": "GROWW_API_KEY and GROWW_SECRET not found in environment"}
            init_fetcher(api_key=api_key, secret=secret)

        if tickers is None:
            tickers = load_nifty500_tickers()
        results = analyse_stocks(tickers, trade_type, top_n)
        return json.dumps(results, default=str)

    except Exception as e:
        logger.error(f"Technical analysis tool failed: {e}")
        return {"error": str(e)}
