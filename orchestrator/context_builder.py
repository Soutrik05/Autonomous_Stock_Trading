# =============================================================================
# orchestrator/context_builder.py
#
# Replaces data_fetcher + embedder + retriever.
#
# Builds a structured context dict at startup (once per run, ~10-20 seconds).
# Provides get_context(symbol, sector) for use in make_final_decision.
# =============================================================================

import yfinance as yf
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 1. THE EXHAUSTIVE NSE SECTOR MAPPING
# Keys: Exact strings from your Nifty 500 CSV
# Values: The closest matching yfinance sector index
CSV_SECTOR_TO_YF_INDEX = {
    "Financial Services":                 "^NSEBANK",
    "Banking":                            "^NSEBANK", # Added just in case
    "Information Technology":             "^CNXIT",
    "Fast Moving Consumer Goods":         "^CNXFMCG",
    "Consumer Staples":                   "^CNXFMCG",
    "Healthcare":                         "^CNXPHARMA",
    "Automobile and Auto Components":     "^CNXAUTO",
    "Automobile":                         "^CNXAUTO",
    "Metals & Mining":                    "^CNXMETAL",
    "Oil Gas & Consumable Fuels":         "^CNXENERGY",
    "Consumer Durables":                  "^CNXCONSUM",
    "Realty":                             "^CNXREALTY",
    "Media, Entertainment & Publication": "^CNXMEDIA",
    "Construction":                       "^CNXINFRA",
    "Capital Goods":                      "^CNXINFRA",
    "Telecommunication":                  "^CNXINFRA",
    "Chemicals":                          "^CRSLDX",  # Fallback to Nifty 500
    "Textiles":                           "^CRSLDX",  # Fallback to Nifty 500
    "General":                            "^CRSLDX",
}

# 2. SECTOR PEERS FOR P/E BENCHMARKING
# We only need these for the major sectors. Others will gracefully return "N/A".
SECTOR_PEERS = {
    "Information Technology":         ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"],
    "Banking":                        ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS"],
    "Financial Services":             ["BAJFINANCE.NS", "BAJAJFINSV.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS"],
    "Fast Moving Consumer Goods":     ["HINDUNILVR.NS", "ITC.NS", "BRITANNIA.NS", "DABUR.NS", "NESTLEIND.NS"],
    "Healthcare":                     ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "LUPIN.NS"],
    "Automobile and Auto Components": ["MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"],
    "Metals & Mining":                ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "SAIL.NS"],
}


class ContextBuilder:
    """
    Built once at startup. All get_context() calls are instant O(1) dict lookups.
    """

    def __init__(self):
        self._stock_bg:   dict[str, str] = {}
        self._sector_ctx: dict[str, str] = {}
        self._market_ctx: str            = ""
        self._built       = False

    def build(self, symbols: list[str]) -> None:
        """
        Call this once before make_final_decision runs.
        symbols: list of NSE tickers WITHOUT .NS suffix.
        """
        print("\n  Building market context (no embeddings — direct lookup)...")
        self._build_market_summary()
        self._build_sector_summaries()
        self._build_stock_backgrounds(symbols)
        self._built = True
        print(f"  Context ready: {len(self._stock_bg)} stocks, "
              f"{len(self._sector_ctx)} sectors\n")

    # ── Public interface ──────────────────────────────────────────────────────

    def get_context(self, symbol: str, sector: str) -> str:
        if not self._built:
            logger.warning("ContextBuilder.build() not called — context empty.")
            return "No market context available."

        stock_bg   = self._stock_bg.get(symbol, f"No background data for {symbol}.")
        
        # If the exact sector string isn't found, fallback to the General/Nifty500 trend
        fallback_sector = self._sector_ctx.get("General", "No broad market data.")
        sector_ctx = self._sector_ctx.get(sector, fallback_sector)

        return (
            f"MARKET OVERVIEW:\n{self._market_ctx}\n\n"
            f"SECTOR CONTEXT ({sector}):\n{sector_ctx}\n\n"
            f"STOCK BACKGROUND ({symbol}):\n{stock_bg}"
        )

    # ── Private builders ──────────────────────────────────────────────────────

    def _build_market_summary(self) -> None:
        try:
            hist = yf.Ticker("^CRSLDX").history(period="1y")
            if hist.empty or len(hist) < 22:
                self._market_ctx = "Nifty 500 data unavailable."
                return
            c         = hist["Close"]
            price     = round(c.iloc[-1], 2)
            high_52w  = round(c.max(), 2)
            low_52w   = round(c.min(), 2)
            r1m       = round(((price - c.iloc[-22]) / c.iloc[-22]) * 100, 2)
            r3m       = round(((price - c.iloc[-66]) / c.iloc[-66]) * 100, 2)
            from_high = round(((price - high_52w) / high_52w) * 100, 2)
            self._market_ctx = (
                f"Nifty 500 — Price: {price}  "
                f"52W High: {high_52w} ({from_high}% from high)  "
                f"52W Low: {low_52w}\n"
                f"1M return: {r1m}%  3M return: {r3m}%\n"
                f"Trend: {'Near highs' if from_high > -5 else 'Mid-range' if from_high > -15 else 'Deep correction'}"
            )
        except Exception as e:
            logger.warning(f"Market summary failed: {e}")
            self._market_ctx = "Nifty 500 data unavailable."

    def _build_sector_summaries(self) -> None:
        # 1. Fetch unique Yahoo indices only once to save network calls
        unique_yf_indices = set(CSV_SECTOR_TO_YF_INDEX.values())
        yf_performance_cache = {}

        for idx_sym in unique_yf_indices:
            try:
                hist = yf.Ticker(idx_sym).history(period="6mo")
                if hist.empty or len(hist) < 22:
                    continue
                c   = hist["Close"]
                r1m = round(((c.iloc[-1] - c.iloc[-22]) / c.iloc[-22]) * 100, 2)
                r3m = round(((c.iloc[-1] - c.iloc[-66]) / c.iloc[-66]) * 100, 2) if len(c) >= 66 else 0
                trend = "Outperforming" if r1m > 2 else "Underperforming" if r1m < -2 else "Neutral"
                
                yf_performance_cache[idx_sym] = {"r1m": r1m, "r3m": r3m, "trend": trend}
            except Exception as e:
                logger.warning(f"Failed to fetch index {idx_sym}: {e}")
                continue

        # 2. Map YF cache back to the granular CSV sector names
        for csv_sector, yf_ticker in CSV_SECTOR_TO_YF_INDEX.items():
            perf = yf_performance_cache.get(yf_ticker)
            if not perf:
                self._sector_ctx[csv_sector] = f"Macro data unavailable for YF proxy {yf_ticker}"
                continue

            # 3. Peer Average P/E logic
            peers      = SECTOR_PEERS.get(csv_sector, [])
            peer_pes   = []
            for p in peers:
                try:
                    # using fast_info or info (info takes slightly longer but has trailingPE)
                    pe = yf.Ticker(p).info.get("trailingPE")
                    if pe and 0 < pe < 200:
                        peer_pes.append(pe)
                except Exception:
                    continue
            avg_pe_str = f"{round(np.mean(peer_pes), 1)}" if peer_pes else "N/A"

            self._sector_ctx[csv_sector] = (
                f"1M: {perf['r1m']}%  3M: {perf['r3m']}%  Trend: {perf['trend']}\n"
                f"Sector peer avg PE: {avg_pe_str}"
            )

    def _build_stock_backgrounds(self, symbols: list[str]) -> None:
        for symbol in symbols:
            try:
                ticker  = yf.Ticker(symbol + ".NS")
                hist    = ticker.history(period="1y")
                
                if hist.empty or len(hist) < 50:
                    continue

                info     = ticker.info
                c        = hist["Close"]
                price    = round(c.iloc[-1], 2)
                high_52w = round(c.max(), 2)
                low_52w  = round(c.min(), 2)
                
                # Position within 52W range (0% = at low, 100% = at high)
                pct_range = round(((price - low_52w) / (high_52w - low_52w + 1e-9)) * 100, 1)
                beta      = info.get("beta", "N/A")
                pe        = info.get("trailingPE", "N/A")

                self._stock_bg[symbol] = (
                    f"52W High: {high_52w}  Low: {low_52w}  "
                    f"Current position in range: {pct_range}%\n"
                    f"Beta: {beta}  Trailing PE: {pe}"
                )
            except Exception as e:
                logger.warning(f"Background for {symbol} failed: {e}")
                continue