"""
Parses Screener.in exported Excel workbooks (.xlsx) from data/screener_raw/
and ingests historical point-in-time quarterly financials into fundamental.db
(fundamental_quarterly_history table).

Enforces SEBI LODR statutory publication floor:
- Quarterly results (Q1, Q2, Q3): period_end_date + 45 calendar days.
- Annual / Q4 results (March quarter): period_end_date + 60 calendar days.

Robust parsing handles Screener's official 'Data Sheet' workbook structure,
resolving fuzzy company names back to exact exchange tickers.
See Plan_v3 Part I §1.1 & Part II §5.6.
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "src"))

from core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_period_string(period_str: str) -> date | None:
    """Parses 'Jun 2025', 'Mar 2026', 'Sep-25' into quarter end calendar date."""
    if not period_str:
        return None
    cleaned = str(period_str).strip().lower().replace("-", " ")
    parts = cleaned.split()
    if len(parts) != 2:
        return None

    month_name, year_str = parts[0], parts[1]
    if month_name not in MONTH_MAP:
        month_name, year_str = parts[1], parts[0]
        if month_name not in MONTH_MAP:
            return None

    try:
        year = int(year_str)
        if year < 100:
            year += 2000
        month = MONTH_MAP[month_name]
        if month in (3, 12):
            day = 31
        elif month in (6, 9):
            day = 30
        else:
            day = 28
        return date(year, month, day)
    except Exception:
        return None


def compute_lodr_filing_date(period_end: date) -> date:
    """
    Computes statutory publication floor under SEBI LODR Regulations:
    - Annual / Q4 (March): 60 days
    - Q1, Q2, Q3: 45 days
    """
    days = 60 if period_end.month == 3 else 45
    return period_end + timedelta(days=days)


def init_quarterly_history_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fundamental_quarterly_history (
            ticker TEXT NOT NULL,
            period_end_date TEXT NOT NULL,
            filing_date TEXT NOT NULL,
            sales REAL,
            operating_profit REAL,
            net_profit REAL,
            eps REAL,
            roce_pct REAL,
            roe_pct REAL,
            debt_to_equity REAL,
            cfo_to_pat REAL,
            pat_growth_yoy_pct REAL,
            promoter_holding_pct REAL,
            borrowings REAL,
            net_worth REAL,
            raw_json TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (ticker, period_end_date)
        );
        CREATE INDEX IF NOT EXISTS idx_fund_qtr_filing ON fundamental_quarterly_history(ticker, filing_date);
    """)
    conn.commit()


def clean_key(s: str) -> str:
    import re

    s = s.upper().replace("&", "AND").replace(".", "").replace("-", " ")
    return re.sub(r"[^A-Z0-9]", "", s)


def build_symbol_resolver(portfolio_db_path: str) -> dict[str, str]:
    """Builds a comprehensive resolver mapping tokens and clean names to tickers."""
    conn = sqlite3.connect(portfolio_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT ticker, company_name FROM symbols").fetchall()
    conn.close()

    resolver = {}
    for r in rows:
        t = r["ticker"].upper()
        cname = r["company_name"].upper()
        resolver[clean_key(t)] = t
        resolver[clean_key(cname)] = t
        clean_cname = cname.replace("LIMITED", "").replace("LTD", "").strip()
        resolver[clean_key(clean_cname)] = t
        if "PHARMACEUTICALS" in cname:
            resolver[clean_key(cname.replace("PHARMACEUTICALS", "PHARMA"))] = t
            resolver[clean_key(clean_cname.replace("PHARMACEUTICALS", "PHARMA"))] = t
        if "CONTROL SYSTEMS" in cname:
            resolver[clean_key(cname.replace("CONTROL SYSTEMS", "CONTROL SYSTEM"))] = t
    return resolver


def resolve_ticker(excel_path: Path, comp_name: str, resolver: dict[str, str]) -> str | None:
    """Resolves canonical ticker from Excel stem or Cell B1 company name."""
    b1_key = clean_key(comp_name)
    stem_key = clean_key(excel_path.stem)

    if b1_key in resolver:
        return resolver[b1_key]
    if stem_key in resolver:
        return resolver[stem_key]

    for k, cand_t in resolver.items():
        if len(k) > 5 and (k in b1_key or b1_key in k or k in stem_key or stem_key in k):
            return cand_t

    return None


def parse_screener_workbook(excel_path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Parses a Screener.in company export workbook from Data Sheet."""
    import openpyxl

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    if "Data Sheet" not in wb.sheetnames:
        raise ValueError(f"'Data Sheet' not found in {excel_path.name}")

    ds = wb["Data Sheet"]
    comp_name = str(ds.cell(1, 2).value or "").strip()

    # Identify master sections
    sections = {}
    for r in range(1, ds.max_row + 1):
        v = ds.cell(r, 1).value
        if v and isinstance(v, str):
            v_str = v.strip()
            if v_str in ("PROFIT & LOSS", "Quarters", "BALANCE SHEET", "CASH FLOW:", "PRICE:", "DERIVED:", "META"):
                sections[v_str] = r

    q_start = sections.get("Quarters")
    if not q_start:
        return comp_name, []

    # 1. Header dates for Quarters
    dates_row = q_start + 1
    quarter_dates = []
    for c in range(2, ds.max_column + 1):
        val = ds.cell(dates_row, c).value
        if val is not None:
            if isinstance(val, (datetime, date)):
                quarter_dates.append((c, val.date() if isinstance(val, datetime) else val))
            elif isinstance(val, str):
                try:
                    dt = datetime.strptime(val.strip()[:10], "%Y-%m-%d").date()
                    quarter_dates.append((c, dt))
                except Exception:
                    pass

    # 2. Extract quarterly line items
    q_items = {}
    for r in range(dates_row + 1, dates_row + 16):
        lbl = ds.cell(r, 1).value
        if not lbl or "BALANCE SHEET" in str(lbl):
            break
        lbl_clean = str(lbl).strip().lower()
        q_items[lbl_clean] = {dt: ds.cell(r, c).value for c, dt in quarter_dates}

    # 3. Extract Balance Sheet for Net Worth and Borrowings
    bs_start = sections.get("BALANCE SHEET")
    bs_dates = []
    bs_items = {}
    if bs_start:
        bs_dates_row = bs_start + 1
        for c in range(2, ds.max_column + 1):
            val = ds.cell(bs_dates_row, c).value
            if val is not None and isinstance(val, (datetime, date)):
                bs_dates.append((c, val.date() if isinstance(val, datetime) else val))
        for r in range(bs_dates_row + 1, bs_start + 25):
            lbl = ds.cell(r, 1).value
            if not lbl or "CASH FLOW" in str(lbl):
                break
            lbl_clean = str(lbl).strip().lower()
            bs_items[lbl_clean] = {dt: ds.cell(r, c).value for c, dt in bs_dates}

    # 4. Extract Cash Flow for Operating Cash Flow (CFO)
    cf_start = sections.get("CASH FLOW:")
    cf_dates = []
    cf_items = {}
    if cf_start:
        cf_dates_row = cf_start + 1
        for c in range(2, ds.max_column + 1):
            val = ds.cell(cf_dates_row, c).value
            if val is not None and isinstance(val, (datetime, date)):
                cf_dates.append((c, val.date() if isinstance(val, datetime) else val))
        for r in range(cf_dates_row + 1, cf_start + 10):
            lbl = ds.cell(r, 1).value
            if not lbl:
                break
            lbl_clean = str(lbl).strip().lower()
            cf_items[lbl_clean] = {dt: ds.cell(r, c).value for c, dt in cf_dates}

    # 5. Build records
    records = []
    for idx, (c, q_dt) in enumerate(quarter_dates):
        sales = q_items.get("sales", {}).get(q_dt)
        op = q_items.get("operating profit", {}).get(q_dt)
        pat = q_items.get("net profit", {}).get(q_dt)
        other_inc = q_items.get("other income", {}).get(q_dt)
        depr = q_items.get("depreciation", {}).get(q_dt)
        interest = q_items.get("interest", {}).get(q_dt)

        # PAT Growth YoY (compared to 4 quarters prior)
        pat_growth_yoy = None
        if idx >= 4:
            prev_q_dt = quarter_dates[idx - 4][1]
            prev_pat = q_items.get("net profit", {}).get(prev_q_dt)
            if prev_pat is not None and abs(prev_pat) > 0.01 and pat is not None:
                pat_growth_yoy = round(((pat - prev_pat) / abs(prev_pat)) * 100.0, 2)

        # Debt to Equity & Net Worth from latest annual Balance Sheet
        de = None
        borrowings = None
        net_worth = None
        roce = None
        roe = None
        if bs_items:
            applicable_bs = [d for c_idx, d in bs_dates if d <= q_dt]
            if applicable_bs:
                latest_bs = applicable_bs[-1]
                eq_cap = bs_items.get("equity share capital", {}).get(latest_bs) or 0.0
                res = bs_items.get("reserves", {}).get(latest_bs) or 0.0
                net_worth = eq_cap + res
                borrowings = bs_items.get("borrowings", {}).get(latest_bs) or 0.0
                if net_worth > 0:
                    de = round(borrowings / net_worth, 4)
                    if pat is not None:
                        roe = round((pat * 4.0 / net_worth) * 100.0, 2)
                    capital_employed = net_worth + borrowings
                    if op is not None and capital_employed > 0:
                        roce = round((op * 4.0 / capital_employed) * 100.0, 2)

        # CFO to PAT
        cfo_pat = None
        if cf_items and pat is not None and abs(pat) > 0.01:
            applicable_cf = [d for c_idx, d in cf_dates if d <= q_dt]
            if applicable_cf:
                latest_cf = applicable_cf[-1]
                cfo = cf_items.get("cash from operating activity", {}).get(latest_cf)
                if cfo is not None:
                    cfo_pat = round(cfo / (pat * 4.0), 2)

        filing_dt = compute_lodr_filing_date(q_dt)

        records.append(
            {
                "period_end_date": q_dt.isoformat(),
                "filing_date": filing_dt.isoformat(),
                "sales": sales,
                "operating_profit": op,
                "net_profit": pat,
                "roce_pct": roce,
                "roe_pct": roe,
                "debt_to_equity": de,
                "cfo_to_pat": cfo_pat,
                "pat_growth_yoy_pct": pat_growth_yoy,
                "borrowings": borrowings,
                "net_worth": net_worth,
                "raw_json": json.dumps(
                    {
                        "sales": sales,
                        "operating_profit": op,
                        "net_profit": pat,
                        "other_income": other_inc,
                        "depreciation": depr,
                        "interest": interest,
                    }
                ),
            }
        )

    return comp_name, records


def ingest_all_workbooks(raw_dir: Path, db_path: str, portfolio_db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    init_quarterly_history_table(conn)

    resolver = build_symbol_resolver(portfolio_db_path)
    files = sorted(list(raw_dir.glob("*.xlsx")))
    logger.info("Found %d workbook(s) in %s", len(files), raw_dir)

    total_ingested = 0
    now_iso = datetime.now().isoformat()

    for excel_path in files:
        try:
            comp_name, records = parse_screener_workbook(excel_path)
            ticker = resolve_ticker(excel_path, comp_name, resolver)
            if not ticker:
                logger.warning("Could not resolve ticker for file %s (Company: '%s')", excel_path.name, comp_name)
                continue

            for r in records:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fundamental_quarterly_history (
                        ticker, period_end_date, filing_date, sales, operating_profit,
                        net_profit, eps, roce_pct, roe_pct, debt_to_equity,
                        cfo_to_pat, pat_growth_yoy_pct, promoter_holding_pct,
                        borrowings, net_worth, raw_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                """,
                    (
                        ticker,
                        r["period_end_date"],
                        r["filing_date"],
                        r["sales"],
                        r["operating_profit"],
                        r["net_profit"],
                        r["roce_pct"],
                        r["roe_pct"],
                        r["debt_to_equity"],
                        r["cfo_to_pat"],
                        r["pat_growth_yoy_pct"],
                        r["borrowings"],
                        r["net_worth"],
                        r["raw_json"],
                        now_iso,
                    ),
                )
                total_ingested += 1

            conn.commit()
            logger.info("Ingested %2d quarters for %-12s (from %s)", len(records), ticker, excel_path.name)
        except Exception as e:
            logger.error("Error parsing %s: %s", excel_path.name, e)

    conn.close()
    logger.info("Completed Screener ingestion: %d total quarter records processed.", total_ingested)
    return total_ingested


def main():
    parser = argparse.ArgumentParser(description="Ingest Screener.in Excel files into fundamental.db")
    parser.add_argument("--raw-dir", default="data/screener_raw", help="Path to raw Excel files")
    parser.add_argument("--db-path", default=settings.FUNDAMENTAL_DB_PATH, help="Path to fundamental.db")
    parser.add_argument("--portfolio-db", default=settings.PORTFOLIO_DB_PATH, help="Path to portfolio.db")
    args = parser.parse_args()

    ingest_all_workbooks(Path(args.raw_dir), args.db_path, args.portfolio_db)


if __name__ == "__main__":
    main()
