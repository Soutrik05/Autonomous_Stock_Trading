# ============================================================
# fundamental_agent/agent.py
#
# The LangChain @tool entry point for the fundamental agent.
# This is the ONLY file the orchestrator interacts with.
#
# Responsibilities:
#   1. Fetch raw data for each ticker (fetcher.py)
#   2. Apply hard disqualification filters (filters.py)
#   3. Score passing stocks (scorer.py)
#   4. Filter to candidates above ORCHESTRATOR_MIN_SCORE threshold
#   5. Build reasoning strings (orchestrator_output.py)
#   6. Save timestamped JSON to disk for audit/history
#   7. Return the clean filtered payload to the orchestrator
# ============================================================

import os
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from langchain.tools import tool

from fundamental_agent import config as cfg
from fundamental_agent.fetcher import fetch_stock_data
from fundamental_agent.filters import apply_hard_filters
from fundamental_agent.scorer import compute_score
from fundamental_agent.orchestrator_output import (
    build_orchestrator_payload,
    save_payload,
)

logger = logging.getLogger("fundamental_agent.agent")


def _load_nifty500() -> List[str]:
    """
    Loads Nifty 500 tickers from news_sentiment/data/ind_nifty500list.csv
    """
    csv_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..",
        "news_sentiment",
        "data",
        "ind_nifty500list.csv"
    ))
    df      = pd.read_csv(csv_path)
    tickers = df["Symbol"].tolist()
    logger.info(f"Loaded {len(tickers)} tickers from {csv_path}")
    return tickers


def _process_ticker(ticker: str) -> tuple:
    """
    Processes a single ticker — fetch, filter, score.
    Runs in a thread pool for parallel execution.
    """
    ticker_clean = ticker.upper().strip()
    ticker_ns    = ticker_clean + cfg.NSE_SUFFIX

    raw     = fetch_stock_data(ticker_ns)
    pat_pct = (
        round(raw["pat_margin"] * 100, 2)
        if raw.get("pat_margin") is not None else None
    )

    record: Dict[str, Any] = {
        "ticker":                  ticker_clean,
        "score":                   0,
        "pe":                      raw.get("pe"),
        "pe_divergence":           raw.get("pe_divergence", False),
        "pe_unreliable":           raw.get("pe_unreliable", False),
        "pb":                      raw.get("pb"),
        "roe_pct":                 round(raw["roe"] * 100, 2) if raw.get("roe") is not None else None,
        "de":                      round(raw["de"], 2)        if raw.get("de")  is not None else None,
        "pat_margin_pct":          pat_pct,
        "eps_growth_pct":          raw.get("eps_growth_pct"),
        "eps_growth_source":       raw.get("eps_growth_source"),
        "fcf_crores":              round(raw["fcf"] / 1e7, 1)          if raw.get("fcf")          is not None else None,
        "operating_cf_crores":     round(raw["operating_cf"] / 1e7, 1) if raw.get("operating_cf") is not None else None,
        "capex_crores":            round(raw["capex"] / 1e7, 1)        if raw.get("capex")        is not None else None,
        "negative_eps_quarters":   raw.get("negative_eps_quarters", 0),
        "sector":                  raw.get("sector"),
        "sector_scoring":          None,
        "metric_scores":           {},
        "weights_used":            {},
        "flags":                   [],
        "confidence":              0.0,
        "disqualified":            False,
        "disqualification_reason": None,
        "fetch_error":             raw.get("fetch_error"),
    }

    if raw.get("fetch_error"):
        logger.error(f"{ticker_clean}: fetch error — {raw['fetch_error']}")
        return ticker_clean, record

    disq_reason = apply_hard_filters(raw)
    if disq_reason:
        logger.info(f"{ticker_clean}: DISQUALIFIED — {disq_reason}")
        record["disqualified"]            = True
        record["disqualification_reason"] = disq_reason
        return ticker_clean, record

    scored = compute_score(raw)
    record["score"]          = scored["final_score"]
    record["metric_scores"]  = scored["metric_scores"]
    record["weights_used"]   = scored["weights_used"]
    record["confidence"]     = scored["confidence"]
    record["flags"]          = scored["flags"]
    record["sector_scoring"] = scored["sector_scoring"]

    logger.info(
        f"{ticker_clean}: score={scored['final_score']}  "
        f"sector={raw.get('sector')}  scoring={scored['sector_scoring']}  "
        f"pe={raw.get('pe')}  eps_src={raw.get('eps_growth_source')}"
    )
    return ticker_clean, record


@tool
def run_fundamental_analysis(tickers: List[str]) -> Dict[str, Any]:
    """
    Screens NSE stocks on fundamental quality and returns only the
    candidates strong enough to pass to technical and sentiment analysis.

    WHEN TO CALL THIS TOOL:
        Only when trade_type is 'medium' (3-6 month investment horizon).
        Do NOT call this tool for 'swing' or 'short' trades.

    Args:
        tickers: Pass an empty list [] — the tool loads the full Nifty
                 500 universe automatically. Do NOT pass tickers yourself.

    Returns:
        {
            "candidates": [
                {"ticker": "HAL", "score": 0.78, "reasoning": "..."},
                ...
            ]
        }
        Extract tickers: [c["ticker"] for c in result["candidates"]]
        Pass to run_technical_analysis and run_sentiment_analysis.
    """
    if not tickers:
        tickers = _load_nifty500()

    logger.info(f"Starting fundamental analysis for {len(tickers)} tickers")
    print(f"⏳  Scanning {len(tickers)} stocks with 20 parallel workers...")

    # ── Parallel fetch + score ────────────────────────────────────────────────
    raw_results: Dict[str, Any] = {}

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_process_ticker, t): t for t in tickers}
        done    = 0
        for future in as_completed(futures):
            try:
                ticker_clean, record = future.result()
                raw_results[ticker_clean] = record
            except Exception as e:
                logger.warning(f"Ticker processing failed: {e}")
            done += 1
            if done % 50 == 0:
                print(f"    {done}/{len(tickers)} processed...")

    print(f"    ✅ {len(raw_results)}/{len(tickers)} stocks processed.")
    logger.info(f"Scoring complete. {len(raw_results)} tickers processed.")

    # ── Build payload ─────────────────────────────────────────────────────────
    payload = build_orchestrator_payload(raw_results)

    # ── Save to disk ──────────────────────────────────────────────────────────
    try:
        filepath = save_payload(payload)
        logger.info(
            f"Payload saved to {filepath}  "
            f"({payload['stocks_passed']}/{payload['stocks_analysed']} passed threshold)"
        )
    except Exception as e:
        logger.warning(f"Failed to save JSON payload to disk: {e}")

    return {"candidates": payload["candidates"]}