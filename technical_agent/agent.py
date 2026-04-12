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
# =============================================================================

import logging
from langchain.tools import tool

from technical_agent.data.data_fetcher import GrowwDataFetcher, is_valid_df
from technical_agent.indicators.support_resistance import compute_support_resistance
from technical_agent.indicators.candlesticks import get_latest_candlestick_patterns
from technical_agent.indicators.rsi import get_latest_rsi
from technical_agent.indicators.macd import compute_macd
from technical_agent.indicators.ema import compute_ema_crossover
from technical_agent.indicators.obv import compute_obv
from technical_agent.scoring.signal_extractor import extract_all_signals
from technical_agent.scoring.scorer import compute_score
from technical_agent.data.data_fetcher import get_market_regime
from technical_agent.scoring.scorer import apply_regime_filter
from technical_agent.config import RISK_PROFILE_THRESHOLDS
from utils import get_sector_map

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

def analyse_stocks(tickers: list, trade_type: str, risk_profile: str = "medium", start_date: str = None) -> dict:
    """
    Runs the full technical analysis pipeline on a list of tickers.

    Args:
        tickers:    List of NSE ticker symbols.
        trade_type: "swing", "short", or "medium"
        start_date:  The scan date upto which technical analysis is to be performed.

    Returns:
        Result dict, sorted by score descending.
    """
    if _fetcher is None:
        raise RuntimeError(
            "Fetcher not initialised. Call init_fetcher(api_key, secret) first."
        )
    
    # --- Market regime check ---
    regime = get_market_regime(end_date=start_date)
    
    sector_map = get_sector_map()
    
    results = []
    for i in range(len(tickers)):
        try:
            ticker = tickers[i]
            print(f"    Analyzing {i+1}/{len(tickers)} : {ticker}", end = "\r")
            # 1. Fetch data
            df = _fetcher.get_ohlcv(ticker, trade_type, end_date=start_date)

            # 2. Validate — skip if insufficient data
            if not is_valid_df(df, ticker, trade_type):
                logger.warning(f"{ticker}: insufficient data for {trade_type} analysis. Skipping.")
                continue
            
            # --- THE LIVE PRICE FIX ---
            # Fetch yesterday's close price
            live_price = df['close'].iloc[-1]
            
            # candlesticks pattern recognition with dynamic volatility and trend context filtering
            cdl_res    = get_latest_candlestick_patterns(df)

            # 3. Compute indicators
            sr_res     = compute_support_resistance(df)
            rsi_value  = get_latest_rsi(df)
            macd_res   = compute_macd(df, trade_type)
            ema_res    = compute_ema_crossover(df, trade_type)
            obv_res    = compute_obv(df)
            
            # 4. Extract signals
            signals = extract_all_signals(rsi_value, macd_res, ema_res, obv_res, sr_res, cdl_res)

            # 5. Score
            score_res = compute_score(signals, trade_type)

            # --- Apply regime filter ---
            score_res = apply_regime_filter(score_res, regime)

            results.append({
                # ── Orchestrator-facing fields ───────────────
                "ticker":             ticker,
                "live_price":         live_price,
                "score":              score_res["score"],
                "sector":             sector_map.get(ticker, "General"),
                "label":              score_res["label"],
                "candlestick_pattern": score_res.get("cdl_reasoning"),
                "reasoning":          score_res.get("reasoning", "Passed technical filters"),
                "nearest_support":    sr_res["nearest_support"],
                "nearest_resistance": sr_res["nearest_resistance"],
                "support_strength":   sr_res["support_strength"],
                # ── Testing/CSV fields ───────────────────────
                # Not used by the orchestrator — ignored silently.
                # Used by technical_main.py for CSV runs and backtesting.
                # Keep in sync with results_to_df() in technical_main.py.
                "signals":            score_res["signals"],
                "sr_proximity_pct":   sr_res.get("sr_proximity_pct"),
                "rsi":                rsi_value,
                "macd_line":          macd_res["macd_line"],
                "signal_line":        macd_res["signal_line"],
                "ema_short":          ema_res["ema_short"],
                "ema_long":           ema_res["ema_long"],
                "obv_slope":          obv_res["obv_slope"],
            })

        except Exception as e:
        # Never crash the entire run for one bad ticker
            logger.warning(f"{ticker}: analysis failed -- {e}")
            continue

    threshold_score = RISK_PROFILE_THRESHOLDS.get(risk_profile.lower(), 0.60)
    recomendations = [r for r in results if r["score"] >= threshold_score]
    recomendations.sort(key=lambda x: x["score"], reverse=True)

    return {
        "market_regime": regime,
        "total_scanned": len(tickers),
        "stocks":        recomendations,
    }


# ---------------------------------------------------------------------------
# LangChain @tool — entry point for the Orchestrator LLM
# ---------------------------------------------------------------------------

@tool
def run_technical_analysis(trade_type: str, tickers: list = None, risk_profile: str = "medium", start_date : str = None) -> dict:
    """
    Runs technical analysis on the given Nifty500 stocks for the given trade type.

    Use this tool when you need to identify technically strong stocks for
    swing trades (2-10 days), short-term trades (2-8 weeks), or medium (3-6 months).
    The tool fetches live data, computes Support/Resistance levels, RSI, MACD, EMA crossovers, and
    OBV for each stock, then returns the top ranked opportunities as a dict.

    Args:
        trade_type: One of "swing", "short", or "medium"
        tickers:    Name of the stocks to run analysis on
        start_date: The scan date you want to perform analysis for. (format: yyyy-mm-dd)
        (if the scan date is current date, you don't need to explicitly provide a start date,
        this argument is only when you want to check past technical analysis) 
    
    For medium trades: pass the tickers list returned by run_fundamental_analysis.
    For swing/short trades: omit tickers — the tool scans the full Nifty 500.

    Returns:
        a dict with keys:
        market_regime:  current Nifty500 market condition
        stocks:         list of candidates having a score greater than a threshold,
                        sorted by score descending, each with ticker, score, label, 
                        reasoning, signals, nearest_support, nearest_resistance,
                        support strength
    """
    if not tickers:
        return {"error": "Technical Agent requires a list of tickers."}
    
    logger.info(f"Technical Agent triggered for {len(tickers)} tickers, trade type '{trade_type.upper()}', risk profile '{risk_profile.upper()}'.")

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

        if not tickers:
            raise ValueError("Technical Agent requires a list of tickers to process.")
        
        results = analyse_stocks(tickers, trade_type,  risk_profile)

        INTERNAL_FIELDS = {
        "signals", "rsi", "macd_line", "signal_line",
        "ema_short", "ema_long", "obv_slope", "sr_proximity_pct"
        }
        clean_stocks = [
            {k: v for k, v in stock.items() if k not in INTERNAL_FIELDS}
            for stock in results["stocks"]
        ]

        logger.info(f"Technical analysis complete: {len(clean_stocks)} / {len(tickers)} selected")

        return {
            "market_regime": results["market_regime"],
            "total_scanned": len(tickers),
            "stocks":        clean_stocks,
        }

    except Exception as e:
        logger.error(f"Technical analysis tool failed: {e}")
        return {"error": str(e)}
