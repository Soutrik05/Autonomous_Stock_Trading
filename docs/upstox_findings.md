# Upstox API Architecture & Findings Specification

Updated as of **2026-10-27** based on exhaustive technical audit against Upstox V2 and V3 API documentation and live endpoint verification using `UPSTOX_ANALYTICS_TOKEN` (never logged, written, or exposed — see `tests/test_upstox_auth.py`). Validated across Nifty 500 constituents (`RELIANCE`: `INE002A01018`, `TCS`: `INE467B01029`, `INFY`: `INE009A01021`, `TATAMOTORS`: `INE155A01022`).

---

## 1. Executive Summary & Deprecation Status

1. **Candles Migration (V2 → V3):**
   - V2 Historical Candle endpoints (`/v2/historical-candle/...`) and Intraday endpoints (`/v2/historical-candle/intraday/...`) are **Deprecated**.
   - V3 endpoints are **Active**:
     - Historical: `GET /v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}` (e.g. `days/1/{to_date}/{from_date}`).
     - Intraday: `GET /v3/historical-candle/intraday/{instrument_key}/{unit}/{interval}` (e.g. `days/1`).
2. **Current-Day EOD Candle Cleared Asynchronously:**
   - The Historical Candle API V3 queries cold analytical storage populated overnight (~23:30–02:00 IST).
   - The Intraday Candle API V3 provides the current day's finalized daily candle immediately upon market close (15:30 IST).
   - Our evening pipeline at 20:00 IST implements a **dual-fetch protocol** (`sync_ohlcv.py` merges today's Intraday daily candle if absent from Historical storage), achieving 100% data integrity without waiting for midnight clearing.
3. **Market Quotes Upgraded to V3:**
   - Endpoint: `GET /v3/market-quote/quotes?instrument_key=...` (batches up to 500 keys in a single HTTP request).
   - Provides official exchange circuit bands (`lower_circuit_limit`, `upper_circuit_limit`), 52-week high/low (`year_high`, `year_low`), 5-depth orderbook, and Call Auction Session (CAS) equilibrium metrics.
4. **Corporate Actions Ground Truth:**
   - Dedicated endpoint: `GET /v2/fundamentals/{isin}/corporate-actions` returns dividends, splits, bonuses, and rights with exact ex-dates, record dates, and adjustment ratios.
   - Eliminates false-positive split detection during market shocks.
5. **Macro Cash Flow Ingestion:**
   - Institutional equity flows available from 1 April 2026 via `GET /v2/market/fii?data_type=NSE_EQ|CASH&interval=1D` and `GET /v2/market/dii?data_type=NSE_EQ|CASH&interval=1D`.
   - Provides daily gross buy/sell values in ₹ Crores.
6. **Curated News Feed:**
   - Dedicated endpoint: `GET /v2/news?category=instrument_keys&instrument_keys=...` (batches up to 30 keys per request).
   - Delivers 7-day curated headlines, summaries, and links mapped to instrument keys, eliminating web scraping risks.

---

## 2. Comprehensive Endpoint Reference & Schema Specifications

### 2.1 Historical Daily Candles (V3 Active)
- **HTTP Method & Path:** `GET /v3/historical-candle/{instrument_key}/days/1/{to_date}/{from_date}`
- **Headers:** `Accept: application/json`, `Authorization: Bearer {token}`
- **Parameters:**
  - `instrument_key`: e.g. `NSE_EQ|INE002A01018`
  - `to_date`: `YYYY-MM-DD`
  - `from_date`: `YYYY-MM-DD`
- **Response Structure:**
  ```json
  {
    "status": "success",
    "data": {
      "candles": [
        ["2026-10-23T00:00:00+05:30", 1215.0, 1222.4, 1205.1, 1218.7, 5421034, 0],
        ["2026-10-22T00:00:00+05:30", 1210.0, 1219.0, 1201.5, 1214.2, 4892011, 0]
      ]
    }
  }
  ```
- **Tuple Schema:** `[timestamp_iso, open, high, low, close, volume, open_interest]`
- **Clearing Cadence:** Cleared and indexed overnight (~23:30 to 02:00 IST). Does not reliably return the current date's candle during evening runs (e.g. 20:00 IST).

### 2.2 Intraday Daily Candle (V3 Active)
- **HTTP Method & Path:** `GET /v3/historical-candle/intraday/{instrument_key}/days/1`
- **Headers:** `Accept: application/json`, `Authorization: Bearer {token}`
- **Parameters:** `instrument_key`: e.g. `NSE_EQ|INE002A01018`
- **Response Structure:**
  ```json
  {
    "status": "success",
    "data": {
      "candles": [
        ["2026-10-26T00:00:00+05:30", 1218.0, 1228.5, 1212.0, 1224.3, 6120440, 0]
      ]
    }
  }
  ```
- **Behavior:** Returns the current day's live/finalized aggregated daily bar immediately after 15:30 IST. Used in `sync_ohlcv.py` to fill today's candle.

### 2.3 Batched Market Quotes (V3 Active)
- **HTTP Method & Path:** `GET /v3/market-quote/quotes?instrument_key={comma_separated_keys}`
- **Headers:** `Accept: application/json`, `Authorization: Bearer {token}`
- **Batch Limit:** Up to 500 instrument keys per HTTP call.
- **Key Response Fields:**
  ```json
  {
    "status": "success",
    "data": {
      "NSE_EQ:RELIANCE": {
        "ohlc": { "open": 1218.0, "high": 1228.5, "low": 1212.0, "close": 1224.3 },
        "depth": {
          "buy": [{"quantity": 1500, "price": 1224.0, "orders": 12}],
          "sell": [{"quantity": 2100, "price": 1224.5, "orders": 18}]
        },
        "last_price": 1224.3,
        "volume": 6120440,
        "prev_close_price": 1218.7,
        "year_high": 1611.8,
        "year_low": 1152.2,
        "lower_circuit_limit": 1163.5,
        "upper_circuit_limit": 1235.3,
        "indicative_equilibrium_price": 1224.0,
        "indicative_imbalance_quantity": 0,
        "reference_price": 1218.7
      }
    }
  }
  ```
- **Usage:**
  - Broker monitor polling (09:20–15:20 IST) via [broker/quotes.py](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/broker/quotes.py).
  - India VIX retrieval (`NSE_INDEX|India VIX`) via [ingestion/sync_macro.py](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/ingestion/sync_macro.py).
  - Exact circuit-lock boundary checks via `lower_circuit_limit` / `upper_circuit_limit`.

### 2.4 Institutional Cash Activity (FII & DII) (V2 Active)
- **HTTP Method & Path:**
  - FII: `GET /v2/market/fii?data_type=NSE_EQ|CASH&interval=1D`
  - DII: `GET /v2/market/dii?data_type=NSE_EQ|CASH&interval=1D`
- **Headers:** `Accept: application/json`, `Authorization: Bearer {token}`
- **Parameters:**
  - `data_type`: `NSE_EQ|CASH` (NSE cash equity segment)
  - `interval`: `1D` (Daily)
- **Response Structure:**
  ```json
  {
    "status": "success",
    "data": {
      "NSE_EQ|CASH": [
        {
          "time_stamp": 1792953000000,
          "buy_amount": 10542.85,
          "sell_amount": 12005.34,
          "buy_contracts": 12450,
          "sell_contracts": 14100
        }
      ]
    }
  }
  ```
- **Calculated Metric:** Amounts are in ₹ Crores.
  $$\text{fii\_net\_cr} = \text{buy\_amount} - \text{sell\_amount}$$
  $$\text{dii\_net\_cr} = \text{buy\_amount} - \text{sell\_amount}$$
- **Usage:** Persisted into `data/macro.db` (`macro_daily` table) by [ingestion/sync_macro.py](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/ingestion/sync_macro.py).

### 2.5 Corporate Actions (V2 Active)
- **HTTP Method & Path:** `GET /v2/fundamentals/{isin}/corporate-actions`
- **Headers:** `Accept: application/json`, `Authorization: Bearer {token}`
- **Response Structure:**
  ```json
  {
    "status": "success",
    "data": [
      {
        "name": "Dividend",
        "expiry_date": "2026-08-19",
        "amount": 10.0,
        "ratio": null,
        "event_details": [
          { "type": "Announcement", "date": "2026-05-15" },
          { "type": "Record Date", "date": "2026-08-20" },
          { "type": "Ex-Date", "date": "2026-08-19" }
        ]
      },
      {
        "name": "Split",
        "expiry_date": "2026-10-10",
        "amount": null,
        "ratio": "1:2",
        "event_details": [
          { "type": "Announcement", "date": "2026-09-01" },
          { "type": "Ex-Date", "date": "2026-10-10" }
        ]
      }
    ]
  }
  ```
- **Usage:** Persisted into `data/fundamental.db` (`corporate_actions` table) by [ingestion/sync_fundamentals.py](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/ingestion/sync_fundamentals.py). Ingestion guards use this table to verify price discontinuities against real corporate actions.

### 2.6 Fundamentals & Financial Statements (V2 Active)
- **Comprehensive Endpoint Catalog & Response Schemas:**
  1. **Company Profile:** `GET /v2/fundamentals/{isin}/profile`
     - Response: `{ "status": "success", "data": { "company_profile": str, "sector": str, "sector_market_cap_inr": { "value": float, "unit": str, "formatted": str }, "sector_market_cap_usd": { "value": float, "unit": str, "formatted": str } } }`
     - Usage: Sector screening (identifying financial companies where DCF is invalid); business description context.
  2. **Key Ratios:** `GET /v2/fundamentals/{isin}/key-ratios`
     - Response: `{ "status": "success", "data": { "key_ratios": [ { "name": "P/E" | "P/B" | "Market Cap" | "EV/EBITDA" | "ROE" | "ROCE" | "ROA", "company_value": float, "sector_value": float } ] } }`
     - Usage: Direct valuation and quality ratios (`roce_pct`, `roe_pct`, `pe`, `pb`).
  3. **Income Statement:** `GET /v2/fundamentals/{isin}/income-statement?type=consolidated&time_period=yearly&fs=true` (also `time_period=quarterly`)
     - Response: `{ "status": "success", "data": { "income_statement": [ { "category": "revenue" | "operating_profit" | "net_profit", "history": [ { "date": str, "amount": float, "change": float } ] } ], "full_statement": [ { "category": "Revenue" | "Operating Profit" | "Profit Before Tax" | "Tax" | "Profit After Tax" | "EPS - Basic" | "EPS - Diluted", "history": [ { "date": str, "amount": float } ] } ] } }`
     - Usage: Multi-period averaged PAT growth ($g$); exact shares outstanding derivation via $\text{PAT (₹ Cr)} \times 10^7 / \text{EPS Basic}$.
  4. **Balance Sheet:** `GET /v2/fundamentals/{isin}/balance-sheet?type=consolidated&fs=true`
     - Response: `{ "status": "success", "data": { "full_statement": [ { "category": "Non-Current Assets" | "Current Assets" | "Total Assets" | "Current Liabilities" | "Net Current Asset" | "Non-Current Liabilities" | "Equity Capital" | "Total Equity & Liabilities", "history": [ { "date": str, "amount": float } ] } ] } }`
     - Usage: Debt-to-Equity proxy; Total Debt deduction in EV-to-Equity bridge ($\text{Current Liabilities} + \text{Non-Current Liabilities}$).
  5. **Cash Flow:** `GET /v2/fundamentals/{isin}/cash-flow?type=consolidated&fs=true`
     - Response: `{ "status": "success", "data": { "full_statement": [ { "category": "Cash flow from Operations" | "Cash flow from Investing" | "Cash flow from Financing" | "Cash (End of the year)", "history": [ { "date": str, "amount": float } ] } ] } }`
     - Usage: $\text{FCFF}_0$ derivation using bounded capex ratio; Cash addition in EV bridge.
  6. **Shareholding:** `GET /v2/fundamentals/{isin}/share-holdings`
     - Response: `{ "status": "success", "data": [ { "category": "promoters" | "fii" | "mutual_funds" | "other_dii" | "retail_and_other", "history": [ { "date": str, "value": float } ] } ] }`
     - Usage: Institutional QoQ delta, promoter stake. (Note: Upstox does not provide pledge details).
  7. **Corporate Actions:** `GET /v2/fundamentals/{isin}/corporate-actions`
     - Response: `{ "status": "success", "data": [ { "name": "Dividend" | "Split" | "Bonus" | "Rights", "expiry_date": str, "amount": float, "ratio": str, "event_details": [ { "type": str, "date": str } ] } ] }`
     - Usage: Corporate action verification and split adjustments in `corporate_actions` table.
  8. **Competitors:** `GET /v2/fundamentals/{isin}/competitors`
     - Response: `{ "status": "success", "data": { "competitors": [ { "isin": str, "company_name": str, "pe": float, "market_cap": float, "close_price": float } ] } }`
     - Usage: Sector peer multiple benchmarking.

### 2.7 Curated News Feed (V2 Active)
- **HTTP Method & Path:** `GET /v2/news?category=instrument_keys&instrument_keys={comma_separated_keys}`
- **Headers:** `Accept: application/json`, `Authorization: Bearer {token}`
- **Batch Limit:** Up to 30 instrument keys per call.
- **Response Structure:**
  ```json
  {
    "status": "success",
    "data": {
      "NSE_EQ|INE002A01018": [
        {
          "heading": "Reliance Retail announces expansion into quick-commerce segment",
          "summary": "Reliance Retail Ventures plans to scale its delivery hubs across tier-1 cities...",
          "thumbnail": "https://img.upstox.com/news/...",
          "article_link": "https://...",
          "published_time": "2026-10-26T14:30:00+05:30"
        }
      ]
    }
  }
  ```
- **Usage:** Persisted into `data/news.db` (`news_articles` table) by [ingestion/sync_news.py](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/ingestion/sync_news.py). Feeds top 3 headlines per candidate into persona decision context.

### 2.8 Market Calendar, Status & Timings (V2 Active)
- **Holidays:** `GET /v2/market/holidays`
  - Returns annual trading calendar with `date`, `description`, `closed_exchanges`, `open_exchanges`. Used to populate `market_calendar` table in `portfolio.db`.
- **Exchange Status:** `GET /v2/market/status/:exchange` (e.g. `NSE`)
  - Statuses: `NORMAL_OPEN`, `PRE_OPEN`, `POST_CLOSE`, `CLOSED`, `cas_eligible_status`.
- **Market Timings:** `GET /v2/market/timings/:date`
  - Returns exact open/close schedule per exchange segment, accommodating special sessions (e.g. Muhurat trading).

### 2.9 WebSockets (V3 & V2 Active)
- **Market Data Feed:** `WSS /v3/feed/market-data-feed` (authorized via `GET /v3/feed/market-data-feed/authorize`).
  - Binary Google Protobuf stream (`MarketDataFeed.proto`).
  - Modes: `ltpc` (LTP + close), `full` (quote + 5-depth orderbook), `full_d30` (30-depth orderbook).
- **Portfolio Stream Feed:** `WSS /v2/feed/portfolio-stream-feed` (authorized via `GET /v2/feed/portfolio-stream-feed/authorize`).
  - Real-time JSON push events for order updates, trade executions, and position updates.

---

## 3. Plan_v3 Metric Availability & Implementation Matrix

| Metric Name | Upstox Source / Mechanism | Schema Status | Ingestion & Contract Notes |
|---|---|---|---|
| `close` | V3 Historical + Intraday `days/1` | **Direct** | Finalized EOD closing price |
| `ema_20/50/200` | Vectorized NumPy from OHLCV | **Computed** | [core/features.py](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/core/features.py) |
| `rsi_14`, `macd_hist`, `adx_14`, `atr_14` | Vectorized NumPy from OHLCV | **Computed** | [core/features.py](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/core/features.py) |
| `volume_surge`, `obv_slope_sign` | Vectorized NumPy from OHLCV | **Computed** | [core/features.py](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/core/features.py) |
| `dist_52w_high_pct`, `dist_52w_low_pct` | V3 Market Quotes (`year_high`, `year_low`) or OHLCV 250-bar rolling | **Direct / Computed** | V3 Quotes provide exchange-official extremes |
| `india_vix` | V3 Market Quote (`NSE_INDEX\|India VIX`) | **Direct** | Daily closing quote in `macro.db` |
| `regime` | Rule-based over VIX bands (`LOW_VOL`, `NORMAL`, `ELEVATED`, `PANIC`) | **Computed** | Evaluated nightly in `macro.db` |
| `fii_net_cr`, `dii_net_cr` | `/v2/market/fii` and `/v2/market/dii` (`NSE_EQ\|CASH`) | **Direct** | Net cash flow ₹ Crores (`buy - sell`) |
| `pe`, `pb` | `/v2/fundamentals/{isin}/key-ratios` | **Direct** | Clamped to `[0, 150]` |
| `peg` | `P/E` ÷ `pat_growth_yoy_pct` | **Computed** | Clamped to `[0, 5]`, `None` if growth $\le 0$ |
| `roce_pct`, `roe_pct` | `/v2/fundamentals/{isin}/key-ratios` | **Direct** | Percentage value |
| `debt_to_equity` | `(Current + Non-Current Liabilities) / Equity Capital` | **Approximation** | Total liabilities proxy (pure borrowings not separated) |
| `interest_coverage` | Upstox API does not provide interest expense | **Omitted / Null** | Gracefully handled as `None` |
| `cfo_to_pat` | `Cash Flow from Operations` ÷ `Profit After Tax` | **Computed** | Annual consolidated ratio |
| `pat_growth_yoy_pct`, `revenue_growth_yoy_pct` | `/v2/fundamentals/{isin}/income-statement` | **Direct** | Extracted from `change` field |
| `promoter_holding_pct` | `/v2/fundamentals/{isin}/share-holdings` | **Direct** | Latest quarter promoter share |
| `promoter_pledge_pct` | Upstox API does not provide pledge details | **Omitted / Null** | Handled as `None` |
| `fii_dii_qoq_delta_pct` | `/v2/fundamentals/{isin}/share-holdings` | **Computed** | QoQ delta in combined FII + DII holding |
| `news_sentiment` | `/v2/news?category=instrument_keys` + FinBERT | **Supported** | Top 3 headlines per ticker |
| `news_article_count` | `/v2/news?category=instrument_keys` | **Direct** | 7-day count per candidate |
| `dcf_iv_share` | Computed in `sync_fundamentals.py` (14-day) | **Computed** | Base intrinsic value per share (₹) |
| `dcf_discount_pct` | Computed in `build_features.py` (Nightly) | **Computed** | `(dcf_iv_share - Close) / Close * 100` (%) |

---

## 3.1 Zerodha Varsity DCF Intrinsic Value Band Specification (Locked)

Based on Zerodha Varsity Module 3 (Chapters 14–15) and empirical audit of Upstox V2 fundamental payloads across Nifty 500 constituents:

### 1. Base Free Cash Flow to Firm ($\text{FCFF}_0$) with Bounded CapEx Deduction
Upstox `/cash-flow` provides `Cash flow from Operations` (CFO) and `Cash flow from Investing` (CFI). Because CFI contains non-operating items (asset sales, acquisitions, liquid investments), the capex deduction is bounded as a fraction of CFO:
$$\text{FCFF}_0 = \text{CFO} \times \left(1 - \text{clamp}\left(\frac{|\text{CFI}|}{\text{CFO}},\ 0.10,\ 0.50\right)\right)$$
- If $\text{CFO} \le 0$: Company is unvaluable by DCF ($\text{FCFF}_0 = \text{None}$).
- If CFI is missing/null: Defaults to median deduction fraction $0.30$ ($\text{FCFF}_0 = 0.70 \times \text{CFO}$).

### 2. Multi-Period Averaged Growth Rate ($g$) with Tight Moderate Clamp
Upstox `/income-statement` provides up to 4 trailing annual periods of `net_profit` with YoY `change` percentages. To eliminate single-year noise (tax credits, low base effect):
$$g_{\text{raw}} = \frac{1}{N} \sum_{i=1}^{N} \text{change}_i$$
$$g = \min(\max(g_{\text{raw}} / 100.0,\ 0.05),\ 0.15)$$
- Winsorized strictly to $[5.0\%, 15.0\%]$ to reflect StockMinds Core's moderate swing profile.

### 3. Sector-Banded Discount Rate ($r$) & Perpetual Growth ($g_T$)
Instead of a flat 12% across heterogeneous risk profiles, discount rates are banded by `symbols.sector`:
- **Defensive Sectors ($r = 11.0\%$):** `Fast Moving Consumer Goods`, `Healthcare`, `Information Technology`.
- **Cyclical / Leveraged Sectors ($r = 13.5\%$):** `Metals & Mining`, `Realty`, `Construction`, `Capital Goods`, `Power`, `Telecommunication`, `Oil Gas & Consumable Fuels`, `Construction Materials`.
- **General / Moderate Sectors ($r = 12.0\%$):** `Automobile and Auto Components`, `Chemicals`, `Consumer Durables`, `Consumer Services`, `Services`, `Textiles`, `Media Entertainment & Publication`, `Diversified`.
- **Financials / Inapplicable ($\text{DCF} = \text{None}$):** `Financial Services` (Banks, NBFCs, Insurance). Omitted gracefully from candidate rows without penalty.
- **Terminal Growth Rate ($g_T$):** Fixed conservative parameter $g_T = 5.0\%$.

### 4. Valuation Engine & Enterprise-to-Equity Bridge
- **5-Year Explicit Stage:** $\text{FCFF}_t = \text{FCFF}_0 \times (1 + g)^t$ for $t \in [1, 5]$.
  $$\text{PV}_{\text{explicit}} = \sum_{t=1}^{5} \frac{\text{FCFF}_t}{(1 + r)^t}$$
- **Terminal Value:** $TV_5 = \frac{\text{FCFF}_5 \times (1 + g_T)}{r - g_T}$.
  $$\text{PV}_{TV} = \frac{TV_5}{(1 + r)^5}$$
- **Enterprise Value:** $\text{EV} = \text{PV}_{\text{explicit}} + \text{PV}_{TV}$.
- **Equity Value Bridge:**
  $$\text{Equity Value} = \text{EV} + \text{Cash (End of the year)} - (\text{Current Liabilities} + \text{Non-Current Liabilities})$$
  *(All items in ₹ Crores)*.
- **Dynamic Shares Outstanding:**
  $$\text{Shares Outstanding} = \frac{\text{Profit After Tax (₹ Cr)} \times 10^7}{\text{EPS - Basic (₹)}}$$
  *(Fallback: $\text{Market Cap (₹ Cr)} \times 10^7 / \text{Price}$ if EPS is missing)*.
- **Per-Share Intrinsic Value:**
  $$\text{IV}_{\text{share}} = \frac{\text{Equity Value (₹ Cr)} \times 10^7}{\text{Shares Outstanding}}$$
  $$\text{IV}_{\text{low}} = 0.90 \times \text{IV}_{\text{share}}, \quad \text{IV}_{\text{high}} = 1.10 \times \text{IV}_{\text{share}}$$

### 5. Split Architecture & Staleness Prevention
- **Slow Cadence (`sync_fundamentals.py` — every 14 days):**
  Computes and stores $\text{IV}_{\text{share}}$, $\text{IV}_{\text{low}}$, $\text{IV}_{\text{high}}$ in `fundamental_ratios` table. Avoids repeated 5-year discounting when financial statements have not changed.
- **Nightly Cadence (`build_features.py` — every evening):**
  Computes $\text{dcf\_discount\_pct}$ fresh using tonight's exact closing price:
  $$\text{dcf\_discount\_pct} = \frac{\text{IV}_{\text{share}} - \text{Close}}{\text{Close}} \times 100$$
  Eliminates the 13-day price staleness bug while preserving compute efficiency.

### 6. Persona Confluence & Agentic Guidance
- **Soft Confluence:** `dcf_discount_pct` is integrated into `varsity_intensity` percentile composite, rewarding undervalued stocks. It is NOT a hard Stage-1 filter, avoiding artificial watchlist starvation.
- **Prompt Guidance:** The LLM is instructed that `dcf_discount_pct` is an estimation model with $\pm 15\%$ modeling uncertainty. The agent prioritizes dual confluence where technical trend structure and DCF fair value band agree.

---

## 4. Architectural Workflows & Codebase Integration

### 4.1 Nightly EOD Ingestion Protocol (20:00 IST)
```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ingestion/cli.py (20:00 IST)                          │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
┌───────────────────────────────────┐               ┌───────────────────────────────┐
│     ingestion/sync_ohlcv.py       │               │    ingestion/sync_macro.py    │
│  1. GET /v3/historical-candle/... │               │  1. GET /v3/market-quote VIX  │
│  2. If today's candle missing:    │               │  2. GET /v2/market/fii CASH   │
│     GET /v3/historical/intraday   │               │  3. GET /v2/market/dii CASH   │
│  3. Check corporate action split  │               │  4. Compute fii/dii net Cr    │
│  4. Upsert into data/ohlcv.db     │               │  5. Store in data/macro.db    │
└────────────────┬──────────────────┘               └───────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        ingestion/sync_fundamentals.py                           │
│  1. GET /v2/fundamentals/{isin}/key-ratios                                      │
│  2. GET /v2/fundamentals/{isin}/income-statement                                │
│  3. GET /v2/fundamentals/{isin}/balance-sheet                                   │
│  4. GET /v2/fundamentals/{isin}/cash-flow                                       │
│  5. GET /v2/fundamentals/{isin}/share-holdings                                  │
│  6. GET /v2/fundamentals/{isin}/corporate-actions -> data/fundamental.db        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Intraday Monitoring Protocol (09:20–15:20 IST)
```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      broker/monitor.py (every 10 minutes)                       │
│  1. Collect all open positions & pending order tickers                          │
│  2. Batch query GET /v3/market-quote/quotes (up to 500 tickers/call)            │
│  3. Read last_price, lower_circuit_limit, upper_circuit_limit                   │
│  4. If price == circuit_limit or volume == 0 -> tag LOCKED_CIRCUIT              │
│  5. Evaluate BUY fills (overshoot allowed) / STOP-LOSS triggers / TARGET signal │
│  6. Execute atomic fills & update positions in state/portfolio.db               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Security & Rate-Limiting Guarantees

1. **Authentication Token Isolation:**
   - Long-lived token stored only in `.env` (`UPSTOX_ANALYTICS_TOKEN`).
   - Token is never written to disk, sqlite databases, or activity logs.
   - Guarded by tests in `tests/test_upstox_auth.py`.
2. **Three-Tier Sliding Window Rate Limiter:**
   - Multi-tier limiter (`core/rate_limiter.py`) throttles calls at:
     - 45 req / 1.0 sec (hard cap 50)
     - 450 req / 60.0 sec (hard cap 500)
     - 1,800 req / 1,800.0 sec (hard cap 2,000)
   - Protects against HTTP 429 rate limit errors during heavy batch runs.
3. **Resilience & Backoff:**
   - HTTP requests employ exponential backoff retries (3 attempts).
   - Unresponsive tickers flagged as `STALE_DATA` after 3 consecutive failures.
