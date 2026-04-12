# ============================================================
# agent.py — LangGraph Tool Interface (Threaded)
# ============================================================

import logging
import concurrent.futures
from typing import List, Dict, Any

from langchain_core.tools import tool

from fundamental_agent.fetcher import fetch_all_fundamentals
from fundamental_agent.filters import passes_hard_filters
from fundamental_agent.scorer import calculate_total_score
from fundamental_agent.output import build_orchestrator_payload, save_payload
from fundamental_agent.config import RISK_THRESHOLDS, DEFAULT_RISK_PROFILE

logger = logging.getLogger(__name__)

@tool
def run_fundamental_analysis(tickers: List[str], risk_profile: str = DEFAULT_RISK_PROFILE) -> Dict[str, Any]:
    """
    Analyzes the fundamental strength of a list of NSE tickers using parallel fetching.
    Fetches data, runs hard disqualification filters, and scores across 4 tiers.
    Only returns stocks that exceed the threshold for the specified risk profile.
    """

    # 0. Resolve the dynamic minimum score from the Config
    min_score = RISK_THRESHOLDS.get(risk_profile.lower(), RISK_THRESHOLDS["medium"])
    logger.info(f"Fundamental Agent triggered for {len(tickers)} tickers.")
    logger.info(f"Risk Profile: {risk_profile.upper()} | Minimum Score Threshold: {min_score}")
    
    # Storage for parallelized fetch results
    raw_fetched_data = {}
    
    # 1. Parallel Unified Data Fetching (YFinance + Screener.in)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        future_to_ticker = {
            executor.submit(fetch_all_fundamentals, ticker): ticker 
            for ticker in tickers
        }
        
        for future in concurrent.futures.as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                # Retrieve result from the thread
                data = future.result()
                if data:
                    raw_fetched_data[ticker] = data
            except Exception as e:
                logger.error(f"[{ticker}] Network fetch error: {e}")

    # Results to pass to the orchestrator builder
    processed_results = {}

    # 2. Sequential Processing for Filtering and Scoring
    # These steps are fast and CPU-bound, so we process them sequentially
    for ticker, data in raw_fetched_data.items():
        try:
            # 2a. Hard Disqualification Filter
            passed_filters, filter_msg = passes_hard_filters(data)
            if not passed_filters:
                logger.info(f"[{ticker}] Dropped: {filter_msg}")
                continue 
                
            # 2b. Calculate Master Score
            score_report = calculate_total_score(data)
            
            # Bundle for output builder
            processed_results[ticker] = {
                "raw_data": data,
                "score_report": score_report
            }
                
        except Exception as e:
            logger.error(f"[{ticker}] Unexpected error during scoring/filtering: {e}")

    # 3. Build Payload and Reasoning Strings
    payload = build_orchestrator_payload(processed_results, min_score=min_score)
    clean_candidates = [
        {"ticker": c["ticker"],
         "score": c["score"],
         "archetype": c.get("archetype", "Unknown"),
         "reasoning": c["reasoning"],
        "sector": c.get("metrics", {}).get("sector", "Unknown"), }
        for c in payload["candidates"]
    ]
    
    # 4. Save to disk for audit
    try:
        filepath = save_payload(payload)
        logger.info(
            f"Payload saved to {filepath} "
            f"({payload['stocks_passed']}/{len(tickers)} passed threshold)"
        )
    except Exception as e:
        logger.warning(f"Failed to save JSON payload to disk: {e}")

    logger.info(f"Fundamental Analysis complete. {len(clean_candidates)}/{len(tickers)} passed.")
    
    return {
        "candidates": clean_candidates
    }