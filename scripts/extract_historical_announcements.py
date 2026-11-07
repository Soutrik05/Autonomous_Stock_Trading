"""
Historical NSE Corporate Announcements Extractor.
Extracts official regulatory disclosures for backtest candidate universe
using jugaad-data, stores them in storage/market/news.db, and runs local FinBERT scoring.
See Plan_v3 Part I §1.1 & Part II §5.6.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta

sys.path.insert(0, "src")
sys.path.insert(0, ".")

try:
    from jugaad_data.nse import NSELive
except ImportError:
    print("Error: jugaad-data is not installed. Please run 'pip install jugaad-data'")
    sys.exit(1)

from core.config import settings
from features.sentiment import get_finbert_scorer


def parse_sort_date_to_iso(sort_date_str: str) -> str:
    """Parses '2026-10-19 11:30:07' to '2026-10-19T11:30:07+05:30'."""
    try:
        dt = datetime.strptime(sort_date_str.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")
    except Exception:
        pass
    # Fallback try an_dt: "19-Oct-2026 11:30:07"
    try:
        dt = datetime.strptime(sort_date_str.strip(), "%d-%b-%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")
    except Exception:
        # Fallback to current time
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30")


def load_candidate_symbols(candidates_file: str = "data/backtest_candidates.json") -> set[str]:
    if not os.path.exists(candidates_file):
        raise FileNotFoundError(f"Candidate file not found: {candidates_file}")
    with open(candidates_file) as f:
        data = json.load(f)
    return set(data.get("tickers", []))


def load_symbol_metadata(portfolio_db_path: str) -> dict[str, dict]:
    conn = sqlite3.connect(portfolio_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT ticker, instrument_key, isin, company_name FROM symbols").fetchall()
    conn.close()
    return {r["ticker"]: dict(r) for r in rows}


def fetch_announcements_with_retry(nse_live: NSELive, start_d: date, end_d: date, max_retries: int = 3) -> list[dict]:
    """Fetches announcements for a date chunk with retry and backoff."""
    for attempt in range(1, max_retries + 1):
        try:
            res = nse_live.corporate_announcements(segment="equities", from_date=start_d, to_date=end_d)
            if isinstance(res, list):
                return res
            return []
        except Exception as e:
            print(f"    [Warning] Attempt {attempt}/{max_retries} failed for {start_d} to {end_d}: {e}")
            if attempt < max_retries:
                time.sleep(2.0 * attempt)
                # Re-initialize session on error
                try:
                    nse_live = NSELive()
                except Exception:
                    pass
            else:
                print(f"    [Error] Skipping chunk {start_d} to {end_d} after {max_retries} attempts.")
                return []


def main():
    parser = argparse.ArgumentParser(description="Extract historical corporate announcements from NSE.")
    parser.add_argument("--start-date", default="2025-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", default="2026-10-29", help="End date YYYY-MM-DD")
    parser.add_argument("--chunk-days", type=int, default=14, help="Date chunk size in days")
    parser.add_argument("--candidates-file", default="data/backtest_candidates.json", help="Candidates JSON file")
    parser.add_argument("--skip-finbert", action="store_true", help="Skip FinBERT sentiment scoring")
    parser.add_argument("--batch-size", type=int, default=32, help="FinBERT scoring batch size")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print("HISTORICAL CORPORATE ANNOUNCEMENTS INGESTION")
    print(f"Range: {args.start_date} to {args.end_date} (Chunk size: {args.chunk_days} days)")
    print("=" * 70)

    candidates = load_candidate_symbols(args.candidates_file)
    print(f"Loaded {len(candidates)} candidate tickers to track.")

    symbols_meta = load_symbol_metadata(settings.PORTFOLIO_DB_PATH)
    print(f"Loaded metadata for {len(symbols_meta)} symbols from portfolio.db.")

    news_conn = sqlite3.connect(settings.NEWS_DB_PATH)
    news_conn.row_factory = sqlite3.Row

    # Ensure news_articles table exists
    news_conn.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_key     TEXT NOT NULL,
            ticker             TEXT NOT NULL,
            heading            TEXT NOT NULL,
            summary            TEXT,
            article_link       TEXT,
            thumbnail          TEXT,
            published_time     TEXT NOT NULL,
            positive_prob      REAL,
            negative_prob      REAL,
            neutral_prob       REAL,
            sentiment_score    REAL,
            confidence         REAL,
            created_at         TEXT NOT NULL,
            UNIQUE (instrument_key, published_time, heading)
        )
    """)
    news_conn.commit()

    curr_start = date.fromisoformat(args.start_date)
    final_end = date.fromisoformat(args.end_date)

    nse_live = NSELive()
    total_inserted = 0
    total_fetched = 0

    print("\nStarting announcement ingestion...")
    while curr_start <= final_end:
        curr_end = min(curr_start + timedelta(days=args.chunk_days - 1), final_end)
        print(f"  Fetching window {curr_start} to {curr_end}...", end="", flush=True)

        records = fetch_announcements_with_retry(nse_live, curr_start, curr_end)
        total_fetched += len(records)

        # Filter for candidates
        matched_records = [r for r in records if r.get("symbol") in candidates]
        print(f" total: {len(records):5d} | candidate matches: {len(matched_records):3d}", end="", flush=True)

        inserted_chunk = 0
        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30")

        for r in matched_records:
            ticker = r["symbol"]
            meta = symbols_meta.get(ticker, {})
            inst_key = meta.get("instrument_key", f"NSE_EQ|{r.get('sm_isin', ticker)}")

            # Heading: combine desc and concise subject
            desc = r.get("desc") or "Corporate Announcement"
            heading = desc.strip()
            summary = (r.get("attchmntText") or desc).strip()
            article_link = r.get("attchmntFile")
            raw_date = r.get("sort_date") or r.get("an_dt") or str(curr_start)
            pub_time = parse_sort_date_to_iso(raw_date)

            try:
                news_conn.execute(
                    """
                    INSERT OR IGNORE INTO news_articles
                    (instrument_key, ticker, heading, summary, article_link, thumbnail, published_time, created_at)
                    VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                    (inst_key, ticker, heading, summary, article_link, pub_time, now_iso),
                )
                if news_conn.total_changes:
                    inserted_chunk += 1
            except Exception:
                pass

        news_conn.commit()
        total_inserted += inserted_chunk
        print(f" | new inserted: {inserted_chunk:3d}")

        curr_start = curr_end + timedelta(days=1)
        time.sleep(1.5)  # Polite pause to avoid exchange throttle

    print(f"\nIngestion Complete! Fetched: {total_fetched}, New candidate articles inserted: {total_inserted}")

    # FinBERT Scoring Phase
    if not args.skip_finbert:
        unscored = news_conn.execute(
            "SELECT id, heading, summary FROM news_articles WHERE sentiment_score IS NULL"
        ).fetchall()
        print(f"\nFound {len(unscored)} articles requiring FinBERT sentiment scoring.")

        if unscored:
            scorer = get_finbert_scorer()
            batch_size = args.batch_size
            total_unscored = len(unscored)

            for i in range(0, total_unscored, batch_size):
                chunk = unscored[i : i + batch_size]
                # Combine heading + summary for rich financial sentiment
                texts = [f"{r['heading']}. {r['summary'][:400] if r['summary'] else ''}" for r in chunk]
                scores = scorer.score_batch(texts, batch_size=batch_size)

                for row, score_dict in zip(chunk, scores):
                    news_conn.execute(
                        """
                        UPDATE news_articles SET
                            positive_prob = ?,
                            negative_prob = ?,
                            neutral_prob = ?,
                            sentiment_score = ?,
                            confidence = ?
                        WHERE id = ?
                    """,
                        (
                            score_dict.get("positive_prob"),
                            score_dict.get("negative_prob"),
                            score_dict.get("neutral_prob"),
                            score_dict.get("sentiment_score"),
                            score_dict.get("confidence"),
                            row["id"],
                        ),
                    )
                news_conn.commit()
                processed = min(i + batch_size, total_unscored)
                print(f"  FinBERT Scored [{processed}/{total_unscored}] articles...", flush=True)

            print("All articles successfully scored with FinBERT.")
    else:
        print("\nFinBERT scoring skipped per --skip-finbert flag.")

    news_conn.close()
    print("\nExtraction job finished.")


if __name__ == "__main__":
    main()
