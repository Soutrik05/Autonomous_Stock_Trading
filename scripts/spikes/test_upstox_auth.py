"""
Day-1 Upstox spike. Standalone script, NOT part of the pytest suite (run it directly,
`python tests/test_upstox_auth.py`, not via `pytest`). It makes real calls against the live
Upstox API for RELIANCE, TCS and HDFCBANK, and prints a structured summary used to write
docs/upstox_findings.md. The access token is read from the environment and is never printed,
logged or included in any recorded field.
See Plan_v3 §1.1.
"""

import json
import os
import time
from datetime import date, timedelta
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.upstox.com"
TOKEN = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
SLEEP_SEC = 0.6  # core/rate_limiter.py has no logic yet; sleep between calls instead

# ISINs taken from data/nifty500_constituents.csv / the symbols table
ISINS = {
    "RELIANCE": "INE002A01018",
    "TCS": "INE467B01029",
    "HDFCBANK": "INE040A01034",
}
# instrument_keys built as NSE_EQ|<ISIN>, for the candle/quote endpoints
STOCKS = {symbol: f"NSE_EQ|{isin}" for symbol, isin in ISINS.items()}

results = []


def call(name: str, method: str, path_template: str, path_args: tuple = (), params: dict = None) -> None:
    """Makes one real HTTP call and records the outcome. `path_args` are quoted into
    `path_template` (instrument_keys contain '|' and must be percent-encoded in the URL path).
    Never logs the Authorization header or the token value."""
    path = path_template.format(*[quote(a, safe="") for a in path_args])
    url = f"{BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}
    record = {
        "name": name,
        "method": method,
        "path": path,
        "params": params or {},
    }
    try:
        resp = requests.request(method, url, headers=headers, params=params, timeout=15)
        try:
            body = resp.json()
        except ValueError:
            body = None
        record["status_code"] = resp.status_code
        record["works"] = resp.status_code == 200
        record["top_level_fields"] = sorted(body.keys()) if isinstance(body, dict) else None
        record["error_snippet"] = None if resp.status_code == 200 else str(body)[:300]
        if resp.status_code == 200:
            record["category"] = "OK"
        elif resp.status_code in (401, 403):
            # Distinct from 404: the endpoint exists, but this token/plan is not allowed to call it.
            record["category"] = "TOKEN_NOT_ALLOWED"
        elif resp.status_code == 404:
            record["category"] = "NOT_FOUND"
        else:
            record["category"] = "OTHER_ERROR"
    except requests.RequestException as exc:
        record["status_code"] = None
        record["works"] = False
        record["top_level_fields"] = None
        record["error_snippet"] = f"{type(exc).__name__}: {exc}"[:300]
        record["category"] = "REQUEST_FAILED"
    results.append(record)
    time.sleep(SLEEP_SEC)


def main() -> None:
    if not TOKEN:
        print("UPSTOX_ANALYTICS_TOKEN is not set in the environment. Aborting spike.")
        return

    today = date.today()
    to_date = (today - timedelta(days=1)).isoformat()
    from_date = (today - timedelta(days=15)).isoformat()

    # 1. Historical daily candles: one call per stock.
    for symbol, instrument_key in STOCKS.items():
        call(
            f"historical_candle_{symbol}",
            "GET",
            "/v2/historical-candle/{}/day/" + to_date + "/" + from_date,
            path_args=(instrument_key,),
        )

    # 2. Batched market quote: one call covering all 3 instruments.
    call(
        "market_quote_batched",
        "GET",
        "/v2/market-quote/quotes",
        params={"instrument_key": ",".join(STOCKS.values())},
    )

    # 3-8. Fundamentals, using the documented /v2/fundamentals/{isin}/... paths
    # (https://upstox.com/developer/api-documentation/get-key-ratios etc.), for all 3 stocks.
    for symbol, isin in ISINS.items():
        call(f"key_ratios_{symbol}", "GET", "/v2/fundamentals/{}/key-ratios", path_args=(isin,))
        call(
            f"income_statement_yearly_{symbol}",
            "GET",
            "/v2/fundamentals/{}/income-statement",
            path_args=(isin,),
            params={"type": "consolidated", "time_period": "yearly", "fs": "true"},
        )
        call(
            f"income_statement_quarterly_{symbol}",
            "GET",
            "/v2/fundamentals/{}/income-statement",
            path_args=(isin,),
            params={"type": "consolidated", "time_period": "quarterly", "fs": "true"},
        )
        call(
            f"balance_sheet_{symbol}",
            "GET",
            "/v2/fundamentals/{}/balance-sheet",
            path_args=(isin,),
            params={"type": "consolidated", "fs": "true"},
        )
        call(
            f"cash_flow_{symbol}",
            "GET",
            "/v2/fundamentals/{}/cash-flow",
            path_args=(isin,),
            params={"type": "consolidated", "fs": "true"},
        )
        call("corporate_actions_" + symbol, "GET", "/v2/fundamentals/{}/corporate-actions", path_args=(isin,))
        call("shareholding_" + symbol, "GET", "/v2/fundamentals/{}/share-holdings", path_args=(isin,))

    # 9. FII/DII market flows: documented market-wide endpoints (not per-stock).
    call("fii_data", "GET", "/v2/market/fii", params={"data_type": "NSE_EQ|CASH", "interval": "1D"})
    call("dii_data", "GET", "/v2/market/dii", params={"data_type": "NSE_EQ|CASH", "interval": "1D"})

    # 10. India VIX quote via the documented market-quote endpoint (VIX is just an index instrument).
    call("india_vix_quote", "GET", "/v2/market-quote/quotes", params={"instrument_key": "NSE_INDEX|India VIX"})

    # 11. Exchange holiday list.
    call("exchange_holidays", "GET", "/v2/market/holidays")

    print(json.dumps(results, indent=2))
    print("\n--- summary ---")
    for r in results:
        print(f"{r['name']:<22} {r['method']:<4} {r['path']:<60} status={r['status_code']} works={r['works']}")


if __name__ == "__main__":
    main()
