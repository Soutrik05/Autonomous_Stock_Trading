"""
Generate candidate universe for walk-forward backtest by running the actual
Stage 0 -> Stage 3 watchlist funnel across 12 sampled dates across the backtest windows.
"""

import json
import sqlite3
import sys
from collections import Counter, defaultdict

import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from agents.personas import all_personas
from core.config import settings
from features.builder import compute_snapshot_features
from watchlist.watchlist_refresh import stage1_filter, stage2_sort


def main():
    print("Connecting to databases...")
    ohlcv_conn = sqlite3.connect("storage/market/ohlcv.db")
    ohlcv_conn.row_factory = sqlite3.Row
    fund_conn = sqlite3.connect("storage/market/fundamental.db")
    fund_conn.row_factory = sqlite3.Row
    port_conn = sqlite3.connect("storage/ledger/portfolio.db")
    port_conn.row_factory = sqlite3.Row
    macro_conn = sqlite3.connect("storage/market/macro.db")
    macro_conn.row_factory = sqlite3.Row

    # Sample 12 dates across the active backtest windows (sessions 200 to 521)
    db_dates = [
        r[0] for r in ohlcv_conn.execute("SELECT DISTINCT trade_date FROM ohlcv ORDER BY trade_date").fetchall()
    ]
    sample_indices = [200, 230, 260, 290, 320, 350, 380, 410, 440, 470, 500, 521]
    sampled_dates = [db_dates[i] for i in sample_indices if i < len(db_dates)]

    print(f"Sampled {len(sampled_dates)} dates across active backtest windows:\n{sampled_dates}")

    fund_rows = {r["ticker"]: dict(r) for r in fund_conn.execute("SELECT * FROM fundamental_ratios").fetchall()}
    symbols = {r["ticker"]: r["sector"] for r in port_conn.execute("SELECT ticker, sector FROM symbols").fetchall()}
    personas = [p for p in all_personas() if p.id != "baseline-simons-rules"]

    print("Pre-loading OHLCV into memory...")
    all_candles = pd.read_sql(
        "SELECT ticker, trade_date, open, high, low, close, volume FROM ohlcv ORDER BY ticker, trade_date ASC",
        ohlcv_conn,
    )
    candles_by_ticker = {ticker: group for ticker, group in all_candles.groupby("ticker")}
    print(f"Loaded {len(candles_by_ticker)} tickers.")

    # Frequency tracking
    watchlist_frequency = Counter()
    persona_appearances = defaultdict(lambda: defaultdict(int))
    max_intensity = defaultdict(float)

    for i, as_of_date in enumerate(sampled_dates, 1):
        print(f"\n[{i}/{len(sampled_dates)}] Processing date {as_of_date}...")

        # Macro
        macro_row = macro_conn.execute(
            "SELECT india_vix, regime FROM macro_daily WHERE trade_date = ?", (as_of_date,)
        ).fetchone()
        vix = macro_row["india_vix"] if macro_row else 15.0
        regime = macro_row["regime"] if macro_row else "RANGE_BOUND"

        # Bulk Stage 0 check for all active tickers
        active_tickers = [
            r["ticker"] for r in port_conn.execute("SELECT ticker FROM symbols WHERE is_active = 1").fetchall()
        ]
        status_map = {
            r["ticker"]: r["status"] for r in ohlcv_conn.execute("SELECT ticker, status FROM ticker_status").fetchall()
        }
        ok_tickers = [t for t in active_tickers if status_map.get(t) == "OK"]

        # Compute features once for tickers passing Stage 0
        features_cache = {}
        for ticker in ok_tickers:
            df = candles_by_ticker.get(ticker)
            if df is None:
                continue
            sub = df[df["trade_date"] <= as_of_date]
            if len(sub) < 30:
                continue

            # Adv20 & turnover check
            adv20 = float(sub["volume"].tail(20).mean())
            latest_close = float(sub["close"].iloc[-1])
            if adv20 * latest_close < settings.MIN_TURNOVER_RUPEES:
                continue

            frow = fund_rows.get(ticker)
            feat = compute_snapshot_features(sub, vix, regime, fundamental_row=frow)
            features_cache[ticker] = feat

        print(f"  Stage 0 / Liquid tickers with features: {len(features_cache)}")

        # Run Stage 1 -> 3 for each persona
        for persona in personas:
            # Stage 0 momentum rule if applicable
            s0_survivors = []
            for t in features_cache:
                df = candles_by_ticker[t]
                sub = df[df["trade_date"] <= as_of_date]
                adv20 = float(sub["volume"].tail(20).mean())
                sma5 = float(sub["volume"].tail(5).mean())
                if persona.id in ("simons", "jhunjhunwala") and not (sma5 > adv20):
                    continue
                s0_survivors.append(t)

            # Stage 1: Hurdles
            s1_survivors = stage1_filter(s0_survivors, features_cache, persona)
            if not s1_survivors:
                continue

            # Stage 2: Intensity Rank
            ranked = stage2_sort(s1_survivors, features_cache, symbols, persona)
            if not ranked:
                continue

            # Stage 3: Sector Cap (max per sector) & Target Size (8-10)
            sector_counts = defaultdict(int)
            final_watchlist = []
            sector_cap = getattr(persona, "sector_cap", settings.SECTOR_CAP_PER_AGENT)
            target_size_max = getattr(persona, "max_candidates", settings.WATCHLIST_TARGET_SIZE_MAX)

            for item in ranked:
                t = item["ticker"]
                sec = symbols.get(t, "UNKNOWN")
                if sector_counts[sec] >= sector_cap:
                    continue
                # EMA 200 trend filter
                if getattr(persona, "require_above_ema200", True):
                    feat = features_cache.get(t)
                    if feat and feat.get("close") and feat.get("ema_200") and feat["close"] <= feat["ema_200"]:
                        continue

                sector_counts[sec] += 1
                final_watchlist.append(item)
                if len(final_watchlist) >= target_size_max:
                    break

            for item in final_watchlist:
                t = item["ticker"]
                watchlist_frequency[t] += 1
                persona_appearances[persona.id][t] += 1
                if item.get("intensity_score", 0) > max_intensity[t]:
                    max_intensity[t] = item.get("intensity_score", 0)

    print("\n" + "=" * 60)
    print("FUNNEL DISCOVERY SUMMARY ACROSS 12 DATES")
    print("=" * 60)
    for p in personas:
        print(f"Persona {p.id:15s}: {len(persona_appearances[p.id])} unique tickers made it into watchlist")

    # Union of all tickers that appeared in any watchlist
    all_selected = set(watchlist_frequency.keys())
    print(f"\nTotal unique tickers in watchlist union: {len(all_selected)}")

    # Ensure balanced representation across all personas:
    # 1. Take top 15 from each persona (ensures Lynch, Marks, RJ, Varsity, Simons all represented)
    curated_set = set()
    for p in personas:
        top_p = [t for t, count in Counter(persona_appearances[p.id]).most_common(20)]
        curated_set.update(top_p)
        print(f"  Persona {p.id:15s} top 20 contributes {len(top_p)} tickers. Curated set now: {len(curated_set)}")

    # 2. Fill the remaining spots up to ~90-100 from highest overall watchlist frequency
    for t, count in watchlist_frequency.most_common():
        if len(curated_set) >= 95:
            break
        curated_set.add(t)

    sorted_candidates = sorted(list(curated_set))
    print(f"\nFinal Curated Candidate Universe: {len(sorted_candidates)} tickers.")

    # Save to data/backtest_candidates.json and data/backtest_candidates.txt
    output_json = {
        "count": len(sorted_candidates),
        "method": "Stage 0->3 Funnel Discovery across 12 bi-monthly dates",
        "sampled_dates": sampled_dates,
        "tickers": sorted_candidates,
        "persona_breakdown": {
            p.id: sorted([t for t in sorted_candidates if t in persona_appearances[p.id]]) for p in personas
        },
    }

    with open("data/backtest_candidates.json", "w") as f:
        json.dump(output_json, f, indent=2)

    with open("data/backtest_candidates.txt", "w") as f:
        for t in sorted_candidates:
            f.write(f"{t}\n")

    print(
        f"Successfully written {len(sorted_candidates)} tickers to data/backtest_candidates.json and data/backtest_candidates.txt"
    )


if __name__ == "__main__":
    main()
