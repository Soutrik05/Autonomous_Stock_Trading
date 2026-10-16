# Upstox Day-1 Spike Findings

Ran against the live Upstox v2 API on 2026-10-16 using the real `UPSTOX_ANALYTICS_TOKEN` from
`.env` (never logged or written anywhere — see `tests/test_upstox_auth.py`), for RELIANCE, TCS
and HDFCBANK (ISINs from the `symbols` table / `data/nifty500_constituents.csv`:
`INE002A01018`, `INE467B01029`, `INE040A01034`).

**Correction (this revision):** the first pass of this spike guessed fundamentals paths that
don't exist on Upstox and wrongly concluded Upstox has no fundamentals API. It does — the
correct paths use the bare ISIN under `/v2/fundamentals/{isin}/...`, documented at
[upstox.com/developer/api-documentation](https://upstox.com/developer/api-documentation/get-key-ratios)
(Key Ratios, Income Statement, Balance Sheet, Cash Flow, Corporate Actions, Share Holdings) and
under `/v2/market/fii` and `/v2/market/dii` (FII/DII Activity Data, under "Market Information").
Retested below with the documented paths: **every one of the 23 fundamentals calls (7 endpoints
× 3 stocks, minus balance-sheet/cash-flow which have no quarterly variant) returned 200** — the
analytics token is fully allowed for all of them, no 401/403 anywhere.

## Endpoint results

| Endpoint | Path | Works | Fields |
|---|---|---|---|
| Historical daily candles (×3 stocks) | `GET /v2/historical-candle/{instrument_key}/day/{to_date}/{from_date}` | **Yes** (200) | `data.candles`: `[timestamp, open, high, low, close, volume, open_interest]` rows |
| Batched market quote (all 3 in one call) | `GET /v2/market-quote/quotes?instrument_key=<comma-separated>` | **Yes** (200) | `data["NSE_EQ:<SYMBOL>"]`: `ohlc, depth, timestamp, instrument_token, symbol, last_price, volume, average_price, oi, net_change, total_buy_quantity, total_sell_quantity, lower_circuit_limit, upper_circuit_limit, last_trade_time, oi_day_high, oi_day_low` |
| India VIX quote | `GET /v2/market-quote/quotes?instrument_key=NSE_INDEX|India VIX` | **Yes** (200) | Same shape as the equity quote above |
| Exchange holiday list | `GET /v2/market/holidays` | **Yes** (200) | `data`: list of `{date, description, holiday_type, closed_exchanges, open_exchanges}` |
| **Key ratios** | `GET /v2/fundamentals/{isin}/key-ratios` | **Yes** (200), all 3 stocks | `data[]`: `{name, company_value, sector_value}`. Real `name` values returned: `P/E, P/B, ROA, ROE, ROCE, Quick Ratio, EV/EBITDA` |
| **Income statement, yearly** | `GET /v2/fundamentals/{isin}/income-statement?type=consolidated&time_period=yearly&fs=true` | **Yes** (200), all 3 stocks | `data.income_statement[]`: `{category: revenue\|operating_profit\|net_profit, history[]: {value, period, change}}`, **4 yearly periods** (Mar 2023–Mar 2026). `data.full_statement[]` (from `fs=true`, always annual): `{particular, history[]}` for `Revenue, Other Income, Total Revenue, Total Expenses, Profit Before Tax, Tax, Profit After Tax, EPS - Basic, EPS - Diluted`, **4 years** |
| **Income statement, quarterly** | same path, `time_period=quarterly` | **Yes** (200), all 3 stocks | Same `income_statement[]` shape, **4 quarterly periods** (Sep 2025–Jun 2026). `full_statement` is unaffected by `time_period` — always the 4 annual periods above |
| **Balance sheet** | `GET /v2/fundamentals/{isin}/balance-sheet?type=consolidated&fs=true` | **Yes** (200), all 3 stocks | `data.history[]`: `{total_asset, total_liability, period}`, **4 yearly periods**. `data.full_statement[]`: `Non-Current Assets, Current Assets, Total Assets, Current Liabilities, Net Current Asset, Non-Current Liabilities, Equity Capital, Total Equity & Liabilities` — no quarterly option exists for this endpoint |
| **Cash flow** | `GET /v2/fundamentals/{isin}/cash-flow?type=consolidated&fs=true` | **Yes** (200), all 3 stocks | `data.cash_flow[]`: `{category: operating\|investing\|financing, history[]}`, **4 yearly periods**. `data.full_statement[]`: `Profit before tax, Income before WC changes, Change in Assets, Change in Liabilities, Change in WC, Cash flow from Operations, Cash flow from Investing, Cash flow from Financing, Total Cash Flow, Cash (Start of the year), Cash (End of the year)` — no quarterly option |
| **Corporate actions** | `GET /v2/fundamentals/{isin}/corporate-actions` | **Yes** (200), all 3 stocks | `data[]`: `{name, expiry_date, amount, ratio, event_details[]}` — dividends/bonus/split/rights with announcement/ex/record dates |
| **Shareholding** | `GET /v2/fundamentals/{isin}/share-holdings` | **Yes** (200), all 3 stocks | `data[]`: `{category, history[]}`. Real categories returned: `promoters, fii, other_dii, mutual_funds, retail_and_other`, **4 quarterly periods** (Sep 2025–Jun 2026). **No pledge field or category exists anywhere in this response.** |
| **FII activity (cash segment)** | `GET /v2/market/fii?data_type=NSE_EQ\|CASH&interval=1D` | **Yes** (200) | `data["NSE_EQ\|CASH"][]`: `{time_stamp, buy_amount, sell_amount, buy_contracts, sell_contracts, oi_contracts, oi_amount, total_long_contracts, total_short_contracts, total_call_long_contracts, total_put_long_contracts, total_call_short_contracts, total_put_short_contracts}`. **30 daily rows** (max per request). Market-wide, not per-stock. Data only from **1 Apr 2026 onward** |
| **DII activity (cash segment)** | `GET /v2/market/dii?data_type=NSE_EQ\|CASH&interval=1D` | **Yes** (200) | Same shape as FII above, **30 daily rows**, market-wide, data only from 1 Apr 2026 onward |

## Answers

**Does the analytics token work for live quotes?**
Yes — unchanged from the first pass.

**Are PEG, interest coverage, promoter pledging, ROCE and D/E present, or must they be computed?**
Mixed, now that the correct paths are used:
- **ROCE: present directly** — `key-ratios` returns it as `ROCE` (e.g. `"10.39%"`).
- **PEG: not present**, but **computable** — `key-ratios` gives `P/E`, and yearly `net_profit` history from `income-statement` gives the earnings growth rate needed for PEG = P/E ÷ earnings-growth%.
- **D/E (debt-to-equity): not present as a ratio, and not cleanly computable either.** `balance-sheet`'s `full_statement` has `Equity Capital` but only aggregate `Current Liabilities` / `Non-Current Liabilities` — there is no separate interest-bearing-debt (borrowings) line item, so `(Current + Non-Current Liabilities) / Equity Capital` is a **total-liabilities-to-equity proxy**, not true D/E. Flag this as an approximation, not drop it.
- **Interest coverage: not present, and not computable from these endpoints** — the income-statement `full_statement` has `Profit Before Tax` but no separate `Interest Expense` line item, so EBIT/interest-expense cannot be derived from what's returned.
- **Promoter pledging: not present anywhere.** `share-holdings` breaks down ownership by category (`promoters, fii, other_dii, mutual_funds, retail_and_other`) but has no pledge figure at all, for any stock tested.

**How many years of quarterly data do we get?**
- `income-statement?time_period=quarterly`: **4 quarters** (the trailing year, Sep 2025–Jun 2026).
- `share-holdings` (shareholding is always reported quarterly, no `time_period` param): **4 quarters** (Sep 2025–Jun 2026).
- `balance-sheet` and `cash-flow` have **no quarterly option at all** — yearly only (4 years), confirmed by their documented query parameters (`type`, `fs` — no `time_period`).
- `income-statement`'s annual `full_statement` (triggered by `fs=true`) is **always 4 years**, regardless of the `time_period` query value.

## Plan_v3 §2.1 persona metrics: availability

Technical metrics (`close`, `ema_20/50/200`, `ema_20_above_50`, `rsi_14`, `macd_hist`, `adx_14`,
`atr_14`, `volume_surge`, `obv_slope_sign`, `dist_52w_high_pct`, `dist_52w_low_pct`) are
**computable** from the historical-candle OHLCV data confirmed working. `india_vix` is
**returned directly** (live quote); `regime` is **computable** (Python rule over VIX bands, not
an API field). No change from the first pass on any of these.

| Feature | Status | Detail |
|---|---|---|
| `roce_pct` | **Returned directly** | `key-ratios` → `ROCE` |
| `roe_pct` | **Returned directly** | `key-ratios` → `ROE` |
| `pe` | **Returned directly** | `key-ratios` → `P/E` |
| `pb` | **Returned directly** | `key-ratios` → `P/B` |
| `peg` | **Computable** | from `key-ratios.P/E` ÷ earnings growth % derived from `income-statement`'s yearly `net_profit` history |
| `debt_to_equity` | **Computable, but only as an approximation** | `(Current Liabilities + Non-Current Liabilities) / Equity Capital` from `balance-sheet.full_statement` — this is total-liabilities-to-equity, not true interest-bearing debt-to-equity, since no borrowings line item is returned |
| `interest_coverage` | **Truly missing** | no `Interest Expense` (or equivalent) line item in `income-statement.full_statement`; cannot be derived from any field returned |
| `cfo_to_pat` | **Computable** | `cash-flow.full_statement` → `Cash flow from Operations` ÷ `income-statement.full_statement` → `Profit After Tax`, same annual periods |
| `pat_growth_yoy_pct` | **Returned directly** (as a ready-made % change) | `income-statement.income_statement[category=net_profit].history[].change`; also independently computable from the raw yearly values |
| `revenue_growth_yoy_pct` | **Returned directly** | same mechanism, `category=revenue` |
| `promoter_holding_pct` | **Returned directly** | `share-holdings` → `category=promoters` |
| `promoter_pledge_pct` | **Truly missing** | no pledge field or category anywhere in `share-holdings`, confirmed across all 3 stocks. Recommend **drop**, or source from an external shareholding-pledge disclosure feed if this metric is kept |
| `fii_dii_qoq_delta_pct` | **Computable, with caveats** | `market/fii` + `market/dii` (`data_type=NSE_EQ\|CASH`) give daily net flow (`buy_amount − sell_amount`); aggregate into quarters to get a QoQ delta. This is **market-wide, not per-stock** (same caveat as before), and **history only starts 1 Apr 2026**, so quarter-over-quarter comparisons will be thin for some time |
| `news_sentiment`, `news_article_count` | Unaffected | sourced via `news_sentiment/`'s own RSS/FinBERT pipeline, not Upstox |

No token, API key, or other personal/account data is included anywhere in this document.
