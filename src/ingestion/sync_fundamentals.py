"""
Syncs financial statements, key ratios, and shareholding into fundamental.db on a 14-day cadence.
Calculates derived metrics (PEG, debt-to-equity proxy, CFO/PAT, YoY growth) for fundamental personas.
See Plan_v3 §1.1, §2.1, and docs/upstox_findings.md.
"""

import argparse
import json
import logging
import sqlite3
from datetime import date

from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from ingestion.upstox_client import UpstoxClient

logger = logging.getLogger(__name__)

JOB_NAME = "sync_fundamentals"

FUNDAMENTAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS fundamental_sync_status (
    ticker          TEXT PRIMARY KEY,
    isin            TEXT NOT NULL,
    last_synced_at  TEXT NOT NULL,
    status          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fundamental_ratios (
    ticker                 TEXT PRIMARY KEY,
    as_of_date             TEXT NOT NULL,
    pe                     REAL,
    pb                     REAL,
    roce_pct               REAL,
    roe_pct                REAL,
    peg                    REAL,
    debt_to_equity         REAL,
    cfo_to_pat             REAL,
    pat_growth_yoy_pct     REAL,
    revenue_growth_yoy_pct REAL,
    promoter_holding_pct   REAL,
    fii_holding_pct        REAL,
    dii_holding_pct        REAL,
    raw_json               TEXT,
    dcf_iv_share           REAL,
    updated_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corporate_actions (
    ticker         TEXT NOT NULL,
    isin           TEXT NOT NULL,
    action_type    TEXT NOT NULL,
    expiry_date    TEXT,
    amount         REAL,
    ratio          TEXT,
    raw_details    TEXT,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (ticker, action_type, expiry_date)
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Creates the fundamental_sync_status and fundamental_ratios tables if not existing."""
    conn.executescript(FUNDAMENTAL_SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(fundamental_ratios)").fetchall()]
    if "dcf_iv_share" not in cols:
        conn.execute("ALTER TABLE fundamental_ratios ADD COLUMN dcf_iv_share REAL")


def _safe_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace("%", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _find_full_statement_latest(full_statement: list[dict], particular_name: str) -> float | None:
    """Finds the most recent historical period value for a given particular/category line item."""
    target = particular_name.strip().lower()
    for item in full_statement:
        particular = (item.get("particular") or item.get("category") or "").strip().lower()
        if particular == target:
            history = item.get("history", [])
            if history and isinstance(history, list):
                first = history[0]
                val = first.get("amount") if "amount" in first else first.get("value")
                return _safe_float(val)
    return None


SECTOR_DISCOUNT_RATES = {
    # Defensive Sectors (11.0%)
    "fast moving consumer goods": 0.11,
    "healthcare": 0.11,
    "information technology": 0.11,
    # Cyclical / Leveraged Sectors (13.5%)
    "metals & mining": 0.135,
    "realty": 0.135,
    "construction": 0.135,
    "capital goods": 0.135,
    "power": 0.135,
    "telecommunication": 0.135,
    "oil gas & consumable fuels": 0.135,
    "construction materials": 0.135,
    # General / Moderate Sectors (12.0%)
    "automobile and auto components": 0.12,
    "chemicals": 0.12,
    "consumer durables": 0.12,
    "consumer services": 0.12,
    "services": 0.12,
    "textiles": 0.12,
    "media entertainment & publication": 0.12,
    "diversified": 0.12,
}


def get_sector_discount_rate(sector: str | None) -> float | None:
    """Returns the discount rate r based on sector, or None for Financial Services."""
    if not sector:
        return 0.12
    sec_lower = sector.strip().lower()
    if sec_lower in ("financial services", "financials", "banking", "banks", "nbfc"):
        return None
    return SECTOR_DISCOUNT_RATES.get(sec_lower, 0.12)


def compute_dcf_intrinsic_value(
    cfo: float | None,
    cfi: float | None,
    cash_end: float | None,
    curr_liab: float | None,
    non_curr_liab: float | None,
    growth_rate: float | None,
    discount_rate: float | None,
    shares_outstanding: float | None,
) -> float | None:
    """
    Computes per-share intrinsic value following Zerodha Varsity Module 3 (Ch 14-15):
    - Returns None if company is in Financial Services (discount_rate is None)
    - Returns None if CFO <= 0 (unvaluable by DCF)
    - FCFF_0 = CFO * (1 - clamp(|CFI| / CFO, 0.10, 0.50))
    - Explicit 5-year discounting: PV_explicit = sum_{t=1}^5 FCFF_t / (1 + r)^t
    - Terminal value at g_T = 5.0%: TV_5 = FCFF_5 * (1 + g_T) / (r - g_T)
    - Enterprise value = PV_explicit + TV_5 / (1 + r)^5
    - Equity value = EV + cash_end - (curr_liab + non_curr_liab)
    - Intrinsic Value per share = Equity Value (in ₹ Cr) * 10^7 / shares_outstanding
    """
    if discount_rate is None or cfo is None or cfo <= 0:
        return None
    if shares_outstanding is None or shares_outstanding <= 0:
        return None

    r = discount_rate
    g_terminal = 0.05
    if r <= g_terminal:
        return None

    # Bounded capex FCFF
    if cfi is not None:
        capex_ratio = min(max(abs(cfi) / cfo, 0.10), 0.50)
    else:
        capex_ratio = 0.30

    fcff_0 = cfo * (1.0 - capex_ratio)
    if fcff_0 <= 0:
        return None

    # Growth rate clamp [0.0%, 15.0%]
    if growth_rate is not None:
        g = min(max(growth_rate, 0.0), 0.15)
    else:
        g = 0.05

    # 5-Year Explicit Stage
    pv_explicit = 0.0
    fcff_t = fcff_0
    for t in range(1, 6):
        fcff_t *= 1.0 + g
        pv_explicit += fcff_t / ((1.0 + r) ** t)

    # Terminal Value
    tv_5 = (fcff_t * (1.0 + g_terminal)) / (r - g_terminal)
    pv_tv = tv_5 / ((1.0 + r) ** 5)

    ev = pv_explicit + pv_tv

    # Equity Value Bridge
    total_debt = (curr_liab or 0.0) + (non_curr_liab or 0.0)
    equity_val = ev + (cash_end or 0.0) - total_debt
    if equity_val <= 0:
        return None

    iv_share = (equity_val * 1e7) / shares_outstanding
    return round(iv_share, 2)


def parse_fundamental_metrics(
    ticker: str,
    as_of_date: str,
    key_ratios: list[dict],
    income_stmt: dict,
    balance_sheet: dict,
    cash_flow: dict,
    share_holdings: list[dict],
    sector: str | None = None,
    current_price: float | None = None,
) -> dict:
    """
    Extracts and derives key fundamental metrics matching the FEATURE_REGISTRY contracts:
    - roce_pct, roe_pct, pe, pb from key-ratios
    - pat_growth_yoy_pct, revenue_growth_yoy_pct from income statement history
    - peg = pe / pat_growth_yoy_pct (if growth > 0)
    - debt_to_equity = (Current + Non-Current Liabilities) / Equity Capital (from balance-sheet)
    - cfo_to_pat = Cash flow from Operations / Profit After Tax
    - promoter_holding_pct, fii_holding_pct, dii_holding_pct from share-holdings
    - dcf_iv_share: Discounted Cash Flow Intrinsic Value per share (Zerodha Varsity Module 3)
    """
    # 1. Key ratios
    ratios_dict = {}
    for r in key_ratios:
        name = r.get("name", "").strip()
        ratios_dict[name] = _safe_float(r.get("company_value"))

    pe = ratios_dict.get("P/E")
    pb = ratios_dict.get("P/B")
    roce_pct = ratios_dict.get("ROCE")
    roe_pct = ratios_dict.get("ROE")

    # 2. Income statement (annual)
    income_categories = {item.get("category"): item for item in income_stmt.get("income_statement", [])}
    pat_growth_yoy_pct = None
    multi_period_growth_pct = None
    if "net_profit" in income_categories:
        history = income_categories["net_profit"].get("history", [])
        changes = []
        for h in history:
            ch = _safe_float(h.get("change"))
            if ch is not None:
                changes.append(ch)
        if changes:
            pat_growth_yoy_pct = changes[0]
            multi_period_growth_pct = sum(changes) / len(changes)
        elif history:
            pat_growth_yoy_pct = _safe_float(history[0].get("change"))
            multi_period_growth_pct = pat_growth_yoy_pct

    revenue_growth_yoy_pct = None
    if "revenue" in income_categories:
        history = income_categories["revenue"].get("history", [])
        if history:
            revenue_growth_yoy_pct = _safe_float(history[0].get("change"))

    # 3. PEG calculation
    peg = None
    if pe is not None and pat_growth_yoy_pct is not None and pat_growth_yoy_pct > 0:
        peg = round(pe / pat_growth_yoy_pct, 4)

    # 4. Debt to Equity proxy: (Current Liabilities + Non-Current Liabilities) / Equity Capital
    bs_full = balance_sheet.get("full_statement", [])
    equity = _find_full_statement_latest(bs_full, "Equity Capital")
    curr_liab = _find_full_statement_latest(bs_full, "Current Liabilities") or 0.0
    non_curr_liab = _find_full_statement_latest(bs_full, "Non-Current Liabilities") or 0.0

    debt_to_equity = None
    if equity is not None and equity > 0:
        debt_to_equity = round((curr_liab + non_curr_liab) / equity, 4)

    # 5. CFO to PAT: Cash flow from Operations / Profit After Tax
    cf_full = cash_flow.get("full_statement", [])
    cfo = _find_full_statement_latest(cf_full, "Cash flow from Operations")
    inc_full = income_stmt.get("full_statement", [])
    pat = _find_full_statement_latest(inc_full, "Profit After Tax")

    cfo_to_pat = None
    if cfo is not None and pat is not None and pat != 0:
        cfo_to_pat = round(cfo / pat, 4)

    # 6. Shareholdings
    holdings_dict = {}
    for h in share_holdings:
        cat = h.get("category", "").strip().lower()
        hist = h.get("history", [])
        if hist and isinstance(hist, list):
            holdings_dict[cat] = _safe_float(hist[0].get("value"))

    promoter_holding_pct = holdings_dict.get("promoters")
    fii_holding_pct = holdings_dict.get("fii")
    other_dii = holdings_dict.get("other_dii") or 0.0
    mf = holdings_dict.get("mutual_funds") or 0.0
    dii_holding_pct = (other_dii + mf) if (other_dii or mf) else holdings_dict.get("dii")

    # 7. Shares Outstanding & DCF Intrinsic Value per share
    # Primary: Market Cap / Price; Fallback: PAT / EPS
    market_cap = ratios_dict.get("Market Cap")
    shares_outstanding = None
    if market_cap is not None and market_cap > 0 and current_price is not None and current_price > 0:
        shares_outstanding = (market_cap * 1e7) / current_price

    if shares_outstanding is None:
        pat_val = _find_full_statement_latest(inc_full, "Profit After Tax")
        eps_val = _find_full_statement_latest(inc_full, "EPS - Basic") or _find_full_statement_latest(inc_full, "EPS")
        if pat_val is not None and pat_val > 0 and eps_val is not None and eps_val > 0:
            shares_outstanding = (pat_val * 1e7) / eps_val

    cfi = _find_full_statement_latest(cf_full, "Cash flow from Investing")
    cash_end = _find_full_statement_latest(cf_full, "Cash (End of the year)") or _find_full_statement_latest(
        cf_full, "Cash (End of year)"
    )

    discount_rate = get_sector_discount_rate(sector)
    growth_dec = (multi_period_growth_pct / 100.0) if multi_period_growth_pct is not None else None

    dcf_iv_share = compute_dcf_intrinsic_value(
        cfo=cfo,
        cfi=cfi,
        cash_end=cash_end,
        curr_liab=curr_liab,
        non_curr_liab=non_curr_liab,
        growth_rate=growth_dec,
        discount_rate=discount_rate,
        shares_outstanding=shares_outstanding,
    )

    raw_payload = {
        "key_ratios": key_ratios,
        "income_statement": income_stmt,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
        "share_holdings": share_holdings,
    }

    return {
        "ticker": ticker,
        "as_of_date": as_of_date,
        "pe": pe,
        "pb": pb,
        "roce_pct": roce_pct,
        "roe_pct": roe_pct,
        "peg": peg,
        "debt_to_equity": debt_to_equity,
        "cfo_to_pat": cfo_to_pat,
        "pat_growth_yoy_pct": pat_growth_yoy_pct,
        "revenue_growth_yoy_pct": revenue_growth_yoy_pct,
        "promoter_holding_pct": promoter_holding_pct,
        "fii_holding_pct": fii_holding_pct,
        "dii_holding_pct": dii_holding_pct,
        "dcf_iv_share": dcf_iv_share,
        "raw_json": json.dumps(raw_payload, default=str),
    }


def is_sync_due(
    fundamental_conn: sqlite3.Connection,
    ticker: str,
    as_of_date: str,
    cadence_days: int = 14,
    force: bool = False,
) -> bool:
    """Checks whether the ticker requires re-fetching based on the 14-day cadence."""
    if force:
        return True

    row = fundamental_conn.execute(
        "SELECT last_synced_at, status FROM fundamental_sync_status WHERE ticker = ?",
        (ticker,),
    ).fetchone()

    if row is None or row["status"] != "SUCCESS":
        return True

    last_sync_str = row["last_synced_at"][:10]  # YYYY-MM-DD
    try:
        last_sync = date.fromisoformat(last_sync_str)
        curr = date.fromisoformat(as_of_date)
        return (curr - last_sync).days >= cadence_days
    except ValueError:
        return True


def sync_ticker(
    fundamental_conn: sqlite3.Connection,
    client: UpstoxClient,
    ticker: str,
    isin: str,
    as_of_date: str,
    clock: Clock,
    sector: str | None = None,
    current_price: float | None = None,
) -> bool:
    """Fetches fundamental data for a single ISIN and updates fundamental_ratios."""
    now_iso = clock.now_iso()
    try:
        key_ratios = client.get_key_ratios(isin)
        income_stmt = client.get_income_statement(isin, time_period="yearly")
        balance_sheet = client.get_balance_sheet(isin)
        cash_flow = client.get_cash_flow(isin)
        share_holdings = client.get_share_holdings(isin)

        metrics = parse_fundamental_metrics(
            ticker=ticker,
            as_of_date=as_of_date,
            key_ratios=key_ratios,
            income_stmt=income_stmt,
            balance_sheet=balance_sheet,
            cash_flow=cash_flow,
            share_holdings=share_holdings,
            sector=sector,
            current_price=current_price,
        )

        fundamental_conn.execute(
            """
            INSERT INTO fundamental_ratios (
                ticker, as_of_date, pe, pb, roce_pct, roe_pct, peg,
                debt_to_equity, cfo_to_pat, pat_growth_yoy_pct, revenue_growth_yoy_pct,
                promoter_holding_pct, fii_holding_pct, dii_holding_pct, raw_json, dcf_iv_share, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                as_of_date = excluded.as_of_date,
                pe = excluded.pe,
                pb = excluded.pb,
                roce_pct = excluded.roce_pct,
                roe_pct = excluded.roe_pct,
                peg = excluded.peg,
                debt_to_equity = excluded.debt_to_equity,
                cfo_to_pat = excluded.cfo_to_pat,
                pat_growth_yoy_pct = excluded.pat_growth_yoy_pct,
                revenue_growth_yoy_pct = excluded.revenue_growth_yoy_pct,
                promoter_holding_pct = excluded.promoter_holding_pct,
                fii_holding_pct = excluded.fii_holding_pct,
                dii_holding_pct = excluded.dii_holding_pct,
                raw_json = excluded.raw_json,
                dcf_iv_share = excluded.dcf_iv_share,
                updated_at = excluded.updated_at
            """,
            (
                ticker,
                as_of_date,
                metrics["pe"],
                metrics["pb"],
                metrics["roce_pct"],
                metrics["roe_pct"],
                metrics["peg"],
                metrics["debt_to_equity"],
                metrics["cfo_to_pat"],
                metrics["pat_growth_yoy_pct"],
                metrics["revenue_growth_yoy_pct"],
                metrics["promoter_holding_pct"],
                metrics["fii_holding_pct"],
                metrics["dii_holding_pct"],
                metrics["raw_json"],
                metrics.get("dcf_iv_share"),
                now_iso,
            ),
        )

        if hasattr(client, "get_corporate_actions"):
            try:
                corp_actions = client.get_corporate_actions(isin)
                for ca in corp_actions:
                    action_type = ca.get("name") or "Unknown"
                    expiry_date = ca.get("expiry_date") or ""
                    amount = ca.get("amount")
                    ratio = ca.get("ratio")
                    raw_details = json.dumps(ca.get("event_details") or [])
                    fundamental_conn.execute(
                        """
                        INSERT INTO corporate_actions
                            (ticker, isin, action_type, expiry_date, amount, ratio, raw_details, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(ticker, action_type, expiry_date) DO UPDATE SET
                            amount = excluded.amount,
                            ratio = excluded.ratio,
                            raw_details = excluded.raw_details,
                            updated_at = excluded.updated_at
                        """,
                        (ticker, isin, action_type, expiry_date, amount, ratio, raw_details, now_iso),
                    )
            except Exception as ca_exc:
                logger.warning("Could not fetch corporate actions for %s (%s): %s", ticker, isin, ca_exc)

        fundamental_conn.execute(
            """
            INSERT INTO fundamental_sync_status (ticker, isin, last_synced_at, status)
            VALUES (?, ?, ?, 'SUCCESS')
            ON CONFLICT(ticker) DO UPDATE SET
                isin = excluded.isin,
                last_synced_at = excluded.last_synced_at,
                status = 'SUCCESS'
            """,
            (ticker, isin, now_iso),
        )
        return True

    except Exception as exc:
        logger.error("Failed to sync fundamentals for %s (%s): %s", ticker, isin, exc)
        fundamental_conn.execute(
            """
            INSERT INTO fundamental_sync_status (ticker, isin, last_synced_at, status)
            VALUES (?, ?, ?, 'FAILED')
            ON CONFLICT(ticker) DO UPDATE SET
                isin = excluded.isin,
                last_synced_at = excluded.last_synced_at,
                status = 'FAILED'
            """,
            (ticker, isin, now_iso),
        )
        return False


def _start_run(conn: sqlite3.Connection, run_date: str, clock: Clock) -> None:
    try:
        conn.execute(
            """
            INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
            VALUES (?, ?, 'RUNNING', ?, NULL, NULL)
            ON CONFLICT(job, run_date) DO UPDATE SET
                status = 'RUNNING', started_at = excluded.started_at, finished_at = NULL, detail = NULL
            """,
            (JOB_NAME, run_date, clock.now_iso()),
        )
    except sqlite3.OperationalError:
        pass


def _finish_run(conn: sqlite3.Connection, run_date: str, status: str, clock: Clock, detail: str = None) -> None:
    try:
        conn.execute(
            "UPDATE pipeline_runs SET status = ?, finished_at = ?, detail = ? WHERE job = ? AND run_date = ?",
            (status, clock.now_iso(), detail, JOB_NAME, run_date),
        )
    except sqlite3.OperationalError:
        pass


def run(
    as_of_date: str = None,
    ticker: str | None = None,
    force: bool = False,
    clock: Clock | None = None,
    portfolio_conn: sqlite3.Connection | None = None,
    fundamental_conn: sqlite3.Connection | None = None,
    client: UpstoxClient | None = None,
) -> dict:
    """
    Executes the fundamental sync pipeline across active symbols in symbols table.
    Enforces 14-day re-fetch cadence unless force=True.
    """
    clock = clock or SystemClock()
    run_date = as_of_date or clock.today().isoformat()

    close_pconn = False
    if portfolio_conn is None:
        portfolio_conn = get_connection(settings.PORTFOLIO_DB_PATH)
        close_pconn = True

    close_fconn = False
    if fundamental_conn is None:
        fundamental_conn = get_connection(settings.FUNDAMENTAL_DB_PATH)
        close_fconn = True

    ensure_schema(fundamental_conn)
    client = client or UpstoxClient()

    summary = {
        "status": "SUCCESS",
        "run_date": run_date,
        "checked": 0,
        "synced": 0,
        "skipped_fresh": 0,
        "failed": 0,
    }

    _start_run(portfolio_conn, run_date, clock)

    try:
        cols = [r[1] for r in portfolio_conn.execute("PRAGMA table_info(symbols)").fetchall()]
        has_sector = "sector" in cols
        select_cols = "ticker, isin, sector" if has_sector else "ticker, isin"

        query = f"SELECT {select_cols} FROM symbols WHERE is_active = 1"
        params = []
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        query += " ORDER BY ticker"

        symbols = portfolio_conn.execute(query, params).fetchall()
        summary["checked"] = len(symbols)

        close_map = {}
        try:
            ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
            close_rows = ohlcv_conn.execute(
                "SELECT ticker, close FROM ohlcv WHERE trade_date <= ? ORDER BY ticker, trade_date DESC",
                (run_date,),
            ).fetchall()
            for r in close_rows:
                t_code = r["ticker"]
                if t_code not in close_map:
                    close_map[t_code] = float(r["close"])
            ohlcv_conn.close()
        except Exception:
            pass

        for sym in symbols:
            sym_ticker = sym["ticker"]
            sym_isin = sym["isin"]
            sym_sector = sym["sector"] if has_sector else None

            if not is_sync_due(fundamental_conn, sym_ticker, run_date, settings.FUNDAMENTAL_REFETCH_DAYS, force=force):
                summary["skipped_fresh"] += 1
                continue

            ok = sync_ticker(
                fundamental_conn=fundamental_conn,
                client=client,
                ticker=sym_ticker,
                isin=sym_isin,
                as_of_date=run_date,
                clock=clock,
                sector=sym_sector,
                current_price=close_map.get(sym_ticker),
            )
            if ok:
                summary["synced"] += 1
            else:
                summary["failed"] += 1

        detail = f"synced={summary['synced']} skipped={summary['skipped_fresh']} failed={summary['failed']}"
        _finish_run(portfolio_conn, run_date, "SUCCESS", clock, detail=detail)

    except Exception as exc:
        _finish_run(portfolio_conn, run_date, "FAILED", clock, detail=str(exc)[:500])
        summary["status"] = "FAILED"
        raise
    finally:
        if close_fconn:
            fundamental_conn.close()
        if close_pconn:
            portfolio_conn.close()

    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Sync fundamental data from Upstox.")
    parser.add_argument("--date", default=None, help="Run date as YYYY-MM-DD")
    parser.add_argument("--ticker", default=None, help="Single ticker to sync")
    parser.add_argument("--force", action="store_true", help="Force re-fetch ignoring 14-day cadence")
    args = parser.parse_args()

    res = run(as_of_date=args.date, ticker=args.ticker, force=args.force)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
