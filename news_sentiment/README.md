# News Sentiment Agent 

Fetches live BSE announcements + financial news, scores them with FinBERT,
and outputs a **weighted sentiment score + signal strength per NIFTY 500 stock**.

## Setup

```bash
pip install -r requirements.txt
```

Drop `ind_nifty500list.csv` into the `data/` folder.

## Run

```bash
python main.py
```

## Output

| Field | Description |
|---|---|
| `matched_symbol` | NSE ticker (e.g. INFY) |
| `matched_company` | Full company name |
| `date` | Date of news |
| `weighted_score` | -1.0 (very negative) to +1.0 (very positive) |
| `signal_strength` | STRONG POSITIVE / POSITIVE / NEUTRAL / NEGATIVE / STRONG NEGATIVE / WEAK |
| `avg_confidence` | FinBERT confidence (0–1) |
| `bse_announcement` | 1 if BSE filing present today, else 0 |
| `article_count` | Number of articles scored for this stock |
| `sources` | Which news sources contributed |

Excel saved to `outputs/layer2_signals.xlsx`.

## For the Orchestrator Agent

Call `run()` from `main.py` — it returns a `list[dict]` payload directly:

```python
from main import run
payload = run()
# payload = [ { matched_symbol, weighted_score, signal_strength, ... }, ... ]
```

## Structure

```
news_sentiment_agent/
├── main.py
├── requirements.txt
├── data/
│   ├── ind_nifty500list.csv   ← you provide this
│   └── fetcher.py
├── layer2/
│   ├── config.py              ← weights & thresholds
│   ├── matcher.py             ← fuzzy match news → NIFTY 500
│   ├── sentiment.py           ← FinBERT scoring
│   └── scoring.py             ← weighted score + signal
└── outputs/
    └── layer2_signals.xlsx    ← generated on run
```