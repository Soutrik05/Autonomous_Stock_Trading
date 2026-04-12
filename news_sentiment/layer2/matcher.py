# layer2/matcher.py

import re
import pandas as pd
from rapidfuzz import fuzz, process
from news_sentiment.layer2.config import FUZZY_THRESHOLD_BSE, FUZZY_THRESHOLD_NEWS, NIFTY500_CSV_PATH


def clean_name(name: str) -> str:
    name = str(name).lower()
    name = re.sub(r'\b(ltd|limited|pvt|private|corp|corporation|co)\b', '', name)
    name = re.sub(r'[^a-z0-9 ]', '', name)
    return re.sub(r'\s+', ' ', name).strip()


def load_nifty500() -> pd.DataFrame:
    df = pd.read_csv(NIFTY500_CSV_PATH)
    df["clean_name"] = df["Company Name"].apply(clean_name)
    print(f"[NIFTY500] Loaded {len(df)} stocks")
    return df


def match_bse_to_nifty(bse_df: pd.DataFrame, nifty500_df: pd.DataFrame) -> pd.DataFrame:
    nifty_names = nifty500_df["clean_name"].tolist()
    bse_df = bse_df.copy()
    bse_df["clean_name"] = bse_df["SLONGNAME"].apply(clean_name)

    def fuzzy_match(name):
        result = process.extractOne(name, nifty_names, scorer=fuzz.token_sort_ratio)
        return result[0] if result and result[1] >= FUZZY_THRESHOLD_BSE else None

    print("[BSE] Fuzzy matching to NIFTY 500...")
    bse_df["matched_clean_name"] = bse_df["clean_name"].apply(fuzzy_match)
    bse_matched = bse_df.dropna(subset=["matched_clean_name"]).copy()

    mapped_df = bse_matched.merge(nifty500_df, left_on="matched_clean_name", right_on="clean_name", how="inner")
    final_df  = mapped_df[["SLONGNAME", "NEWSID", "NEWSSUB", "NEWS_DT", "Company Name", "Industry", "Symbol", "ISIN Code"]].copy()
    print(f"[BSE] Matched {len(final_df)} announcements")
    return final_df


def find_companies_in_text(text: str, nifty500_df: pd.DataFrame) -> list:
    if not isinstance(text, str) or not text.strip():
        return []

    nifty_symbols = nifty500_df["Symbol"].str.upper().tolist()
    nifty_names   = nifty500_df["clean_name"].tolist()
    text_clean    = clean_name(text)
    text_upper    = text.upper()
    matches       = []
    seen          = set()

    for symbol in nifty_symbols:
        if re.search(rf'\b{re.escape(symbol)}\b', text_upper):
            row = nifty500_df[nifty500_df["Symbol"].str.upper() == symbol].iloc[0]
            if symbol not in seen:
                matches.append({"matched_symbol": symbol, "matched_company": row["Company Name"],
                                 "matched_industry": row["Industry"], "match_method": "ticker"})
                seen.add(symbol)

    for i, nifty_name in enumerate(nifty_names):
        if len(nifty_name) < 4:
            continue
        if fuzz.partial_ratio(nifty_name, text_clean) >= FUZZY_THRESHOLD_NEWS:
            row    = nifty500_df.iloc[i]
            symbol = row["Symbol"].upper()
            if symbol not in seen:
                matches.append({"matched_symbol": symbol, "matched_company": row["Company Name"],
                                 "matched_industry": row["Industry"], "match_method": "fuzzy_name"})
                seen.add(symbol)
    return matches


def match_news_to_nifty(news_df: pd.DataFrame, nifty500_df: pd.DataFrame) -> pd.DataFrame:
    news_df = news_df.copy()
    news_df["combined_text"] = news_df["title"].fillna("") + " " + news_df["summary"].fillna("")

    print("[NEWS] Matching companies in articles...")
    news_df["company_matches"] = news_df["combined_text"].apply(
        lambda x: find_companies_in_text(x, nifty500_df)
    )

    mapped = news_df[news_df["company_matches"].map(len) > 0].copy().explode("company_matches")
    match_details = mapped["company_matches"].apply(pd.Series)
    mapped = pd.concat([mapped.drop(columns=["company_matches", "combined_text"]), match_details], axis=1)
    mapped.reset_index(drop=True, inplace=True)
    print(f"[NEWS] {len(mapped)} article-company pairs")
    return mapped