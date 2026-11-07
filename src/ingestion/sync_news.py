"""
Syncs official news from Upstox for Nifty 500 constituents into data/news.db.
Scores newly discovered articles using local FinBERT and stores sentiment scores.
Accumulates rolling historical news across runs so multi-week news history is preserved.
See Plan_v3 §2.4.
"""

import argparse
import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone

from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from features.sentiment import FinBertScorer, get_finbert_scorer
from ingestion.upstox_client import UpstoxClient

logger = logging.getLogger(__name__)

NEWS_SCHEMA = """
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
);
CREATE INDEX IF NOT EXISTS idx_news_ticker_pub ON news_articles(ticker, published_time);
CREATE INDEX IF NOT EXISTS idx_news_inst_pub ON news_articles(instrument_key, published_time);
"""

IST = timezone(timedelta(hours=5, minutes=30))
UPSTOX_NEWS_BATCH_SIZE = 30


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(NEWS_SCHEMA)


def _format_published_time(ts_val) -> str:
    """Converts epoch ms integer or ISO string to standard ISO string in IST."""
    if isinstance(ts_val, (int, float)):
        # Upstox gives epoch ms
        dt = datetime.fromtimestamp(ts_val / 1000.0, tz=IST)
        return dt.isoformat()
    if isinstance(ts_val, str):
        return ts_val
    return datetime.now(tz=IST).isoformat()


def sync_news(
    client: UpstoxClient | None = None,
    clock: Clock | None = None,
    news_conn: sqlite3.Connection | None = None,
    portfolio_conn: sqlite3.Connection | None = None,
    scorer: FinBertScorer | None = None,
    limit: int | None = None,
    ticker: str | None = None,
) -> dict[str, int]:
    """Syncs news from Upstox API for active tickers, runs FinBERT scoring on new articles,
    and upserts into data/news.db.

    Returns: {'tickers_queried': int, 'articles_fetched': int, 'articles_scored': int}
    """
    clock = clock or SystemClock()
    client = client or UpstoxClient()
    scorer = scorer or get_finbert_scorer()

    owns_news = news_conn is None
    news_db = news_conn or get_connection(settings.NEWS_DB_PATH)

    owns_portfolio = portfolio_conn is None
    portfolio_db = portfolio_conn or get_connection(settings.PORTFOLIO_DB_PATH)

    try:
        ensure_schema(news_db)

        # 1. Load active tickers and instrument keys
        query = "SELECT ticker, instrument_key FROM symbols WHERE is_active = 1"
        params = []
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        query += " ORDER BY ticker"
        if limit and not ticker:
            query += f" LIMIT {int(limit)}"

        rows = portfolio_db.execute(query, params).fetchall()
        if not rows:
            logger.info("No active symbols found to sync news.")
            return {"tickers_queried": 0, "articles_fetched": 0, "articles_scored": 0}

        ticker_map: dict[str, str] = {row[1]: row[0] for row in rows}  # instrument_key -> ticker
        instrument_keys: list[str] = [row[1] for row in rows]

        total_fetched = 0
        total_scored = 0
        now_iso = clock.now_iso()

        # 2. Query in batches of up to 30 keys
        for i in range(0, len(instrument_keys), UPSTOX_NEWS_BATCH_SIZE):
            chunk = instrument_keys[i : i + UPSTOX_NEWS_BATCH_SIZE]
            try:
                news_by_key = client.get_news(chunk)
            except Exception as e:
                logger.warning(f"Failed to fetch news chunk {i}-{i + len(chunk)}: {e}")
                continue

            # 3. Filter for articles that are not yet stored in news.db
            new_articles_to_score: list[tuple[str, str, dict]] = []  # (inst_key, tkr, art)
            scoring_texts: list[str] = []

            for inst_key, articles in news_by_key.items():
                tkr = ticker_map.get(inst_key, "")
                if not tkr or not articles:
                    continue

                for art in articles:
                    total_fetched += 1
                    heading = (art.get("heading") or "").strip()
                    if not heading:
                        continue

                    pub_time = _format_published_time(art.get("published_time"))

                    # Check if already in db
                    exists = news_db.execute(
                        "SELECT id, sentiment_score FROM news_articles WHERE instrument_key = ? AND published_time = ? AND heading = ?",
                        (inst_key, pub_time, heading),
                    ).fetchone()

                    if exists and exists[1] is not None:
                        continue  # Already scored

                    # Needs scoring
                    summary = (art.get("summary") or "").strip()
                    text_to_score = f"{heading}. {summary}" if summary else heading
                    new_articles_to_score.append((inst_key, tkr, art))
                    scoring_texts.append(text_to_score)

            # 4. Batch score with FinBERT
            if new_articles_to_score:
                scores = scorer.score_batch(scoring_texts)
                total_scored += len(scores)

                from core.schemas import SanitizedNewsArticle

                for (inst_key, tkr, art), score_res in zip(new_articles_to_score, scores):
                    try:
                        clean_art = SanitizedNewsArticle(
                            ticker=tkr,
                            instrument_key=inst_key,
                            heading=art.get("heading") or "",
                            summary=art.get("summary"),
                            article_link=art.get("article_link"),
                            thumbnail=art.get("thumbnail"),
                            published_time=_format_published_time(art.get("published_time")),
                            positive_prob=score_res.get("positive_prob"),
                            negative_prob=score_res.get("negative_prob"),
                            neutral_prob=score_res.get("neutral_prob"),
                            sentiment_score=score_res.get("sentiment_score"),
                            confidence=score_res.get("confidence"),
                        )
                    except Exception as val_err:
                        logger.warning(f"Skipping malformed news article for {tkr}: {val_err}")
                        continue

                    news_db.execute(
                        """
                        INSERT INTO news_articles (
                            instrument_key, ticker, heading, summary, article_link, thumbnail,
                            published_time, positive_prob, negative_prob, neutral_prob,
                            sentiment_score, confidence, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(instrument_key, published_time, heading) DO UPDATE SET
                            summary = excluded.summary,
                            article_link = excluded.article_link,
                            thumbnail = excluded.thumbnail,
                            positive_prob = excluded.positive_prob,
                            negative_prob = excluded.negative_prob,
                            neutral_prob = excluded.neutral_prob,
                            sentiment_score = excluded.sentiment_score,
                            confidence = excluded.confidence
                        """,
                        (
                            clean_art.instrument_key,
                            clean_art.ticker,
                            clean_art.heading,
                            clean_art.summary,
                            clean_art.article_link,
                            clean_art.thumbnail,
                            clean_art.published_time,
                            clean_art.positive_prob,
                            clean_art.negative_prob,
                            clean_art.neutral_prob,
                            clean_art.sentiment_score,
                            clean_art.confidence,
                            now_iso,
                        ),
                    )
                news_db.commit()

        logger.info(
            f"News sync complete. Queried {len(rows)} tickers, fetched {total_fetched} articles, scored {total_scored} new."
        )
        return {
            "tickers_queried": len(rows),
            "articles_fetched": total_fetched,
            "articles_scored": total_scored,
        }

    finally:
        if owns_news:
            news_db.close()
        if owns_portfolio:
            portfolio_db.close()


def _calc_relative_age(pub_time_str: str, as_of_date_str: str) -> str:
    try:
        pub_date = datetime.fromisoformat(pub_time_str).date()
        as_of = date.fromisoformat(as_of_date_str[:10])
        diff = (as_of - pub_date).days
        if diff <= 0:
            return "today"
        if diff == 1:
            return "1d ago"
        return f"{diff}d ago"
    except Exception:
        return pub_time_str[:10]


def get_ticker_news_sentiment(
    news_conn: sqlite3.Connection,
    ticker: str,
    as_of_date: str,
    lookback_days: int = 7,
) -> tuple[float | None, int, list[dict]]:
    """Calculates aggregate sentiment score and article count for a ticker over a lookback window.
    Returns: (aggregate_sentiment_score, article_count, top_articles)
    where top_articles includes relative_age, truncated heading, and FinBERT score.
    """
    ensure_schema(news_conn)

    start_date = (datetime.fromisoformat(as_of_date[:10]) - timedelta(days=lookback_days)).date().isoformat()
    rows = news_conn.execute(
        """
        SELECT heading, summary, article_link, published_time, sentiment_score, confidence
        FROM news_articles
        WHERE ticker = ? AND published_time >= ? AND published_time <= ? || 'T23:59:59'
        ORDER BY published_time DESC
        """,
        (ticker, start_date, as_of_date[:10]),
    ).fetchall()

    if not rows:
        return 0.0, 0, []

    scores = [r[4] for r in rows if r[4] is not None]
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
    articles = [
        {
            "heading": r[0][:120],  # cut to 120 chars per Plan_v3 §2.4
            "summary": r[1],
            "article_link": r[2],
            "published_time": r[3],
            "sentiment_score": r[4],
            "confidence": r[5],
            "relative_age": _calc_relative_age(r[3], as_of_date),
        }
        for r in rows[:3]  # top 3 most recent articles
    ]
    return avg_score, len(rows), articles


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync official Upstox news and score sentiment with FinBERT.")
    parser.add_argument("--ticker", dest="ticker", default=None, help="Sync single ticker")
    parser.add_argument("--limit", dest="limit", type=int, default=None, help="Limit number of tickers")
    args = parser.parse_args()

    res = sync_news(ticker=args.ticker, limit=args.limit)
    print(f"News sync result: {res}")


if __name__ == "__main__":
    main()
