# Upstox Day-1 Spike Findings

Ran against the live Upstox v2 API on 2026-10-16 using the real `UPSTOX_ANALYTICS_TOKEN` from
`.env` (never logged or written anywhere — see `tests/test_upstox_auth.py`), for RELIANCE, TCS
and HDFCBANK (instrument keys from `data/nifty500_constituents.csv`'s ISIN column:
`NSE_EQ|INE002A01018`, `NSE_EQ|INE467B01029`, `NSE_EQ|INE040A01034`).

## Endpoint results

| Endpoint | Path | Works | Top-level fields |
|---|---|---|---|
| Historical daily candles (×3 stocks) | `GET /v2/historical-candle/{instrument_key}/day/{to_date}/{from_date}` | **Yes** (200) | `data.candles`: list of `[timestamp, open, high, low, close, volume, open_interest]` rows |
| Batched market quote (all 3 in one call) | `GET /v2/market-quote/quotes?instrument_key=<comma-separated>` | **Yes** (200) | `data["NSE_EQ:<SYMBOL>"]`: `ohlc, depth, timestamp, instrument_token, symbol, last_price, volume, average_price, oi, net_change, total_buy_quantity, total_sell_quantity, lower_circuit_limit, upper_circuit_limit, last_trade_time, oi_day_high, oi_day_low` |
| Income statement | `GET /v2/fundamentals/income-statement/{instrument_key}` (guessed, following Upstox's own naming convention) | **No** (404 `Resource not Found`) | — |
| Balance sheet | `GET /v2/fundamentals/balance-sheet/{instrument_key}` (guessed) | **No** (404 `Resource not Found`) | — |
| Cash flow | `GET /v2/fundamentals/cash-flow/{instrument_key}` (guessed) | **No** (404 `Resource not Found`) | — |
| Key ratios | `GET /v2/fundamentals/ratios/{instrument_key}` (guessed) | **No** (404 `Resource not Found`) | — |
| Shareholding | `GET /v2/fundamentals/shareholding/{instrument_key}` (guessed) | **No** (404 `Resource not Found`) | — |
| Corporate actions | `GET /v2/corporate-actions?instrument_key={instrument_key}` (guessed) | **No** (404 `Resource not Found`) | — |
| FII/DII market flows | `GET /v2/market-quote/fii-dii` (guessed) | **No** (400 `Invalid Endpoint`) | — |
| India VIX quote | `GET /v2/market-quote/quotes?instrument_key=NSE_INDEX|India VIX` (same documented quote endpoint, VIX is just an index instrument) | **Yes** (200) | `data["NSE_INDEX:India VIX"]`: same fields as the equity quote above |
| Exchange holiday list | `GET /v2/market/holidays` | **Yes** (200) | `data`: list of `{date, description, holiday_type, closed_exchanges, open_exchanges}` |

## Answers

**Does the analytics token work for live quotes?**
Yes. The batched `market-quote/quotes` call, the historical-candle calls, and the VIX quote all
returned `200` with real market data for all three stocks and the VIX index in a single
authenticated session.

**Are PEG, interest coverage, promoter pledging, ROCE and D/E present, or must they be computed?**
None of them are present. Upstox's v2 API has no fundamentals/financial-statements group at all —
every guessed path under a plausible `/v2/fundamentals/...` or `/v2/corporate-actions` naming
returned a real `404 Resource not Found` from Upstox's own router (not an auth or scope error),
and this matches Upstox's public API documentation, which only covers Login, User, Order,
Portfolio, Charges, Market Quote, Historical Candle, Option Chain and Market Information. ROCE,
D/E, interest coverage and PEG must be **computed from raw financial statements sourced
elsewhere** (not Upstox); promoter pledging must be **sourced from shareholding-pattern filings**
(also not Upstox — this is a disclosure dataset, not a derived ratio, so "compute from statements"
does not apply to it).

**How many years of quarterly data do we get?**
Not applicable to Upstox: there is no statements endpoint to version, so there is no quarterly
history to report from this API. Whatever external source is chosen for fundamentals (see below)
will set its own depth; it was not tested here since it's outside Upstox's API surface.

## Plan_v3 §2.1 persona metrics not available from the Upstox API

Technical metrics (`close`, `ema_20/50/200`, `ema_20_above_50`, `rsi_14`, `macd_hist`, `adx_14`,
`atr_14`, `volume_surge`, `obv_slope_sign`, `dist_52w_high_pct`, `dist_52w_low_pct`) are all
derived in Python from the historical-candle OHLCV data confirmed working above — no change
needed there. `india_vix` and `regime` are also covered: VIX is a live quote (confirmed above)
and `regime` is Python-computed from VIX bands, not an API field.

Everything below needs a decision, since none of it is available from Upstox:

| Feature | Not available because | Suggestion |
|---|---|---|
| `roce_pct`, `roe_pct` | No income statement / balance sheet endpoint | **Compute from statements** — source raw income statement & balance sheet from an external vendor (e.g. screener.in, NSE filings, yfinance), compute in `fundamental/` |
| `pe`, `pb` | No EPS / book-value source (price itself is available) | **Compute from statements** — Upstox gives `last_price`; divide by externally-sourced EPS/book value |
| `peg` | Needs `pe` plus earnings growth, neither sourced from Upstox | **Compute from statements** — depends on the two rows above plus multi-period earnings history |
| `debt_to_equity` | No balance sheet endpoint | **Compute from statements** — externally-sourced balance sheet |
| `interest_coverage` | No income statement endpoint | **Compute from statements** — externally-sourced income statement |
| `cfo_to_pat` | No cash flow or income statement endpoint | **Compute from statements** — externally-sourced cash flow + income statement |
| `pat_growth_yoy_pct`, `revenue_growth_yoy_pct` | No multi-period income statement endpoint | **Compute from statements** — needs ≥2 years of externally-sourced income statements |
| `promoter_holding_pct`, `promoter_pledge_pct` | No shareholding endpoint; this is a disclosure filing, not a derived ratio | **Source externally** (NSE/BSE shareholding-pattern filings or a vendor) — "compute from statements" does not apply; if no reliable external source is picked in week 1, **drop** rather than fabricate |
| `fii_dii_qoq_delta_pct` | No FII/DII flow endpoint; this is market-wide, not per-company | **Drop** from the fundamentals module — if wanted, source it separately from NSE's public daily FII/DII bulletin as a macro feature (§2.5 `macro.db`), not through Upstox or per-stock fundamentals |

No token, API key, or other personal/account data is included anywhere in this document.
