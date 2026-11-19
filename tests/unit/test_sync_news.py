import sqlite3
from unittest.mock import MagicMock

import pytest

from core.clock import FakeClock
from ingestion.sync_news import (
    _format_published_time,
    ensure_schema,
    get_ticker_news_sentiment,
    sync_news,
)


@pytest.fixture
def mem_dbs():
    portfolio_conn = sqlite3.connect(":memory:")
    portfolio_conn.row_factory = sqlite3.Row
    portfolio_conn.execute(
        """
        CREATE TABLE symbols (
            ticker TEXT PRIMARY KEY,
            instrument_key TEXT NOT NULL,
            isin TEXT NOT NULL,
            company_name TEXT NOT NULL,
            sector TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    portfolio_conn.execute(
        "INSERT INTO symbols VALUES ('RELIANCE', 'NSE_EQ|INE002A01018', 'INE002A01018', 'Reliance', 'Energy', 1)"
    )
    portfolio_conn.execute("INSERT INTO symbols VALUES ('TCS', 'NSE_EQ|INE467B01029', 'INE467B01029', 'TCS', 'IT', 1)")
    portfolio_conn.commit()

    news_conn = sqlite3.connect(":memory:")
    news_conn.row_factory = sqlite3.Row
    ensure_schema(news_conn)

    return portfolio_conn, news_conn


def test_format_published_time():
    # Test epoch ms conversion
    epoch_ms = 1793015173687
    res = _format_published_time(epoch_ms)
    assert "2026-10-" in res
    assert "+05:30" in res

    # Test string passthrough
    assert _format_published_time("2026-10-26T14:30:00+05:30") == "2026-10-26T14:30:00+05:30"


def test_sync_news_ingestion_and_deduplication(mem_dbs):
    portfolio_conn, news_conn = mem_dbs
    from datetime import datetime, timedelta, timezone

    ist = timezone(timedelta(hours=5, minutes=30))
    clock = FakeClock(datetime(2026, 10, 26, 20, 0, 0, tzinfo=ist))

    mock_client = MagicMock()
    mock_client.get_news.return_value = {
        "NSE_EQ|INE002A01018": [
            {
                "heading": "Reliance Q2 profit beats estimates",
                "summary": "Net profit jumped 15% YoY with retail driving growth.",
                "article_link": "https://upstox.com/news/1",
                "thumbnail": "https://img.upstox.com/1",
                "published_time": 1793015173687,
            }
        ],
        "NSE_EQ|INE467B01029": [
            {
                "heading": "TCS bags major European cloud deal",
                "summary": "Multi-year deal signed for digital transformation.",
                "article_link": "https://upstox.com/news/2",
                "thumbnail": "https://img.upstox.com/2",
                "published_time": 1793015170000,
            }
        ],
    }

    mock_scorer = MagicMock()
    mock_scorer.score_batch.return_value = [
        {
            "sentiment_score": 0.85,
            "positive_prob": 0.90,
            "negative_prob": 0.05,
            "neutral_prob": 0.05,
            "confidence": 0.90,
            "label": "positive",
        },
        {
            "sentiment_score": 0.60,
            "positive_prob": 0.70,
            "negative_prob": 0.10,
            "neutral_prob": 0.20,
            "confidence": 0.70,
            "label": "positive",
        },
    ]

    # First run: should fetch and score 2 articles
    res = sync_news(
        client=mock_client,
        clock=clock,
        news_conn=news_conn,
        portfolio_conn=portfolio_conn,
        scorer=mock_scorer,
    )

    assert res["tickers_queried"] == 2
    assert res["articles_fetched"] == 2
    assert res["articles_scored"] == 2

    # Verify rows in news_articles
    rows = news_conn.execute("SELECT ticker, sentiment_score, heading FROM news_articles ORDER BY ticker").fetchall()
    assert len(rows) == 2
    assert rows[0]["ticker"] == "RELIANCE"
    assert rows[0]["sentiment_score"] == 0.85
    assert rows[1]["ticker"] == "TCS"
    assert rows[1]["sentiment_score"] == 0.60

    # Second run with same articles: should skip re-scoring
    res2 = sync_news(
        client=mock_client,
        clock=clock,
        news_conn=news_conn,
        portfolio_conn=portfolio_conn,
        scorer=mock_scorer,
    )
    assert res2["articles_fetched"] == 2
    assert res2["articles_scored"] == 0


def test_get_ticker_news_sentiment(mem_dbs):
    _, news_conn = mem_dbs

    news_conn.execute(
        """
        INSERT INTO news_articles (
            instrument_key, ticker, heading, summary, article_link, thumbnail,
            published_time, positive_prob, negative_prob, neutral_prob,
            sentiment_score, confidence, created_at
        ) VALUES
        ('NSE_EQ|INE002A01018', 'RELIANCE', 'Article 1', 'Summary 1', 'link1', 'thumb1', '2026-10-25T10:00:00+05:30', 0.8, 0.1, 0.1, 0.7, 0.8, '2026-10-25T10:00:00+05:30'),
        ('NSE_EQ|INE002A01018', 'RELIANCE', 'Article 2', 'Summary 2', 'link2', 'thumb2', '2026-10-24T10:00:00+05:30', 0.6, 0.1, 0.3, 0.5, 0.6, '2026-10-24T10:00:00+05:30'),
        ('NSE_EQ|INE002A01018', 'RELIANCE', 'Old Article', 'Old Summary', 'link3', 'thumb3', '2026-10-10T10:00:00+05:30', 0.2, 0.7, 0.1, -0.5, 0.7, '2026-10-10T10:00:00+05:30')
        """
    )
    news_conn.commit()

    # Query with 7-day lookback as of 2026-10-26
    avg_score, count, articles = get_ticker_news_sentiment(
        news_conn=news_conn,
        ticker="RELIANCE",
        as_of_date="2026-10-26",
        lookback_days=7,
    )

    # Only Article 1 (0.7) and Article 2 (0.5) should be included (avg = 0.60)
    assert count == 2
    assert avg_score == 0.60
    assert len(articles) == 2
    assert articles[0]["heading"] == "Article 1"

    # Query for non-existent ticker
    avg_infy, count_infy, arts_infy = get_ticker_news_sentiment(
        news_conn=news_conn,
        ticker="INFY",
        as_of_date="2026-10-26",
    )
    assert avg_infy == 0.0
    assert count_infy == 0
    assert arts_infy == []
