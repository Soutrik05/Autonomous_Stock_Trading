# data/fetcher.py

import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd
import requests
import feedparser


# ── BSE Announcements ──────────────────────────────────────────────────────────

def fetch_bse_announcements() -> pd.DataFrame:
    url     = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bseindia.com/"}

    all_announcements = []
    page = 1

    while True:
        params = {
            "pageno": page, "strCat": "-1", "strPrevDate": "",
            "strScrip": "", "strSearch": "P", "strToDate": "",
            "strType": "C", "subcategory": "-1"
        }
        try:
            r = requests.get(url, headers=headers, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[BSE] Page {page} failed: {e}. Stopping.")
            break

        if "Table" in data and data["Table"]:
            print(f"[BSE] Page {page} → {len(data['Table'])} records")
            all_announcements.extend(data["Table"])
            page += 1
            time.sleep(1)
        else:
            print(f"[BSE] No more data at page {page}.")
            break

    df = pd.DataFrame(all_announcements)
    if df.empty:
        return df

    df = df[df["CRITICALNEWS"] == 1].copy()
    print(f"[BSE] Critical announcements: {len(df)}")
    return df


# ── RSS + Google News ──────────────────────────────────────────────────────────

RSS_SOURCES = {
    "Economic Times":    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Mint":              "https://www.livemint.com/rss/markets",
    "NDTV Profit":       "https://feeds.feedburner.com/ndtvprofit-latest",
    "Financial Express": "https://www.financialexpress.com/market/feed/",
}


def _fetch_feed(url: str):
    req = urllib.request.Request(url, headers={
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept":          "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return feedparser.parse(urllib.request.urlopen(req, timeout=10).read())


def fetch_rss_news() -> pd.DataFrame:
    all_news = []

    for name, rss_url in RSS_SOURCES.items():
        print(f"[RSS] Fetching {name}...")
        try:
            feed = _fetch_feed(rss_url)
            if not feed.entries:
                print(f"  [WARN] No entries from {name}")
                continue
            for entry in feed.entries:
                all_news.append({
                    "source":    name,
                    "title":     entry.get("title", ""),
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary":   entry.get("summary", "")
                })
            print(f"  {len(feed.entries)} entries")
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

    # Business Standard via Google News proxy
    try:
        bs_url  = f"https://news.google.com/rss/search?q={urllib.parse.quote('site:business-standard.com markets stocks')}&hl=en-IN&gl=IN&ceid=IN:en"
        bs_feed = feedparser.parse(bs_url)
        for entry in bs_feed.entries:
            published = datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") and entry.published_parsed else None
            all_news.append({
                "source": "Business Standard", "title": entry.get("title", ""),
                "link": entry.get("link", ""), "published": published, "summary": entry.get("summary", "")
            })
        print(f"[RSS] Business Standard (Google proxy): {len(bs_feed.entries)} entries")
    except Exception as e:
        print(f"[ERROR] Business Standard: {e}")

    df = pd.DataFrame(all_news)
    df.drop_duplicates(subset=["title"], inplace=True)
    return df


def fetch_google_news() -> pd.DataFrame:
    today = datetime.today().strftime("%Y-%m-%d")
    query = urllib.parse.quote(
        "NSE OR BSE OR Nifty OR Sensex OR earnings OR quarterly results OR "
        "dividend OR rights issue OR stock split OR buyback OR QIP"
    )
    feed  = feedparser.parse(
        f"https://news.google.com/rss/search?q={query}+after:{today}&hl=en-IN&gl=IN&ceid=IN:en"
    )
    news = []
    for entry in feed.entries:
        published = datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") and entry.published_parsed else None
        news.append({
            "source": "Google News", "title": entry.get("title", ""),
            "link": entry.get("link", ""), "published": published, "summary": entry.get("summary", "")
        })
    df = pd.DataFrame(news)
    df.drop_duplicates(subset=["title"], inplace=True)
    print(f"[Google News] {len(df)} articles")
    return df