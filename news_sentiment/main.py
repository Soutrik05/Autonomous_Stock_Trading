import pandas as pd
from news_sentiment.data.fetcher import fetch_bse_announcements, fetch_rss_news, fetch_google_news
from news_sentiment.layer2.matcher import load_nifty500, match_bse_to_nifty, match_news_to_nifty
from news_sentiment.layer2.sentiment import load_finbert, score_dataframe
from news_sentiment.layer2.scoring import build_layer2_output, get_orchestrator_payload
from news_sentiment.layer2.config import OUTPUT_PATH


COMMON_COLS = [
    "source", "title", "link", "published", "summary",
    "matched_symbol", "matched_company", "matched_industry", "match_method"
]


def run() -> list[dict]:
    # 1. Load NIFTY 500
    nifty500_df = load_nifty500()

    # 2. Fetch live data
    bse_raw  = fetch_bse_announcements()
    rss_df   = fetch_rss_news()
    gnews_df = fetch_google_news()

    # 3. Standardise BSE announcements
    bse_mapped = match_bse_to_nifty(bse_raw, nifty500_df)
    bse_std = bse_mapped.rename(columns={
        "NEWSSUB": "title", "NEWS_DT": "published",
        "SLONGNAME": "company_raw_name", "Symbol": "matched_symbol",
        "Company Name": "matched_company", "Industry": "matched_industry",
    }).copy()
    bse_std["source"]       = "BSE Announcement"
    bse_std["summary"]      = ""
    bse_std["match_method"] = "bse_direct"
    bse_std["link"]         = bse_std["NEWSID"].apply(
        lambda x: f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{x}.pdf"
    )
    bse_std = bse_std[COMMON_COLS]

    # 4. Match news articles to NIFTY 500
    combined_news = pd.concat([rss_df, gnews_df], ignore_index=True)
    combined_news.drop_duplicates(subset=["title"], inplace=True)
    news_mapped = match_news_to_nifty(combined_news, nifty500_df)[COMMON_COLS]

    # 5. Master dataframe
    master_df = pd.concat([bse_std, news_mapped], ignore_index=True)
    master_df.drop_duplicates(subset=["title", "matched_symbol"], inplace=True)
    master_df.reset_index(drop=True, inplace=True)
    print(f"\n[Main] Master news: {len(master_df)} rows | Sources: {master_df['source'].value_counts().to_dict()}")

    # 6. FinBERT scoring
    finbert   = load_finbert()
    scored_df = score_dataframe(finbert, master_df)

    # 7. Weighted aggregation + signal
    daily_df = build_layer2_output(scored_df)

    # 8. Save to Excel
    daily_df.to_excel(OUTPUT_PATH, index=False)
    print(f"\n[Main] Saved → {OUTPUT_PATH}")

    # 9. Return payload for orchestrator
    payload = get_orchestrator_payload(daily_df)
    print(f"[Main] Orchestrator payload ready: {len(payload)} records")
    return payload


if __name__ == "__main__":
    payload = run()

    # Preview what goes to the orchestrator
    print("\n── SAMPLE PAYLOAD (first 5) ──")
    for item in payload[:5]:
        print(item)