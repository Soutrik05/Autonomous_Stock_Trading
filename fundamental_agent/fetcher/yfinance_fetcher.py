# ============================================================
# yfinance_fetcher.py — YFinance Data Retrieval Module
# ============================================================

import logging
import yfinance as yf
import pandas as pd
from typing import Dict, Any

from fundamental_agent import config as cfg

logger = logging.getLogger(__name__)

def _calculate_cagr(latest_val: float, base_val: float, periods: int) -> float:
    if latest_val is None or base_val is None or periods <= 0:
        return None
    if base_val <= 0:
        return None
    if latest_val <= 0:
        return -1.0
    try:
        cagr = ((latest_val / base_val) ** (1 / periods)) - 1
        return round(cagr * 100.0, 2)
    except Exception:
        return None

def fetch_yfinance_data(ticker: str) -> Dict[str, Any]:
    yf_ticker = f"{ticker}{cfg.NSE_SUFFIX}"
    stock = yf.Ticker(yf_ticker)
    
    data = {
        "ticker": ticker,
        "sector": "Unknown",
        "current_price": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "roe_fallback": None,
        "eps_growth_1yr": None,
        "revenue_cagr_3yr": None,
        "profit_cagr_3yr": None,
        "gpm": None,
        "opm": None,
        "receivables_pct_sales": None,
        "m_score_components": {"dsri": None, "gmi": None, "sgi": None, "lvgi": None, "tata": None}
    }

    try:
        info = stock.info
        data["sector"] = info.get("sector", "Unknown")
        data["current_price"] = info.get("currentPrice", info.get("previousClose"))
        data["pe_ratio"] = info.get("trailingPE")
        data["pb_ratio"] = info.get("priceToBook")
        if info.get("returnOnEquity") is not None:
            data["roe_fallback"] = info.get("returnOnEquity") * 100
        if info.get("earningsGrowth") is not None:
            growth_pct = info.get("earningsGrowth") * 100
            data["eps_growth_1yr"] = max(-cfg.CAGR_MAX_CLIP, min(cfg.CAGR_MAX_CLIP, growth_pct))
        if info.get("profitMargins") is not None:
            data["pat_margin"] = info.get("profitMargins") * 100
        if info.get("grossMargins") is not None:
            data["gross_margin"] = info.get("grossMargins") * 100
    except Exception as e:
        logger.debug(f"Failed to fetch YFinance 'info' for {ticker}: {e}")

    latest_revenue = None

    try:
        financials = stock.financials
        if not financials.empty:
            if 'Total Revenue' in financials.index:
                rev_series = financials.loc['Total Revenue']
                if len(rev_series) > 0:
                    latest_revenue = float(rev_series.iloc[0])
                if len(rev_series) > cfg.CAGR_YEARS:
                    base_revenue = float(rev_series.iloc[cfg.CAGR_YEARS])
                    data["revenue_cagr_3yr"] = _calculate_cagr(latest_revenue, base_revenue, cfg.CAGR_YEARS)

            if 'Net Income' in financials.index:
                ni_series = financials.loc['Net Income']
                if len(ni_series) > cfg.CAGR_YEARS:
                    latest_ni = float(ni_series.iloc[0])
                    base_ni = float(ni_series.iloc[cfg.CAGR_YEARS])
                    data["profit_cagr_3yr"] = _calculate_cagr(latest_ni, base_ni, cfg.CAGR_YEARS)

            if 'Gross Profit' in financials.index and latest_revenue and latest_revenue > 0:
                latest_gp = float(financials.loc['Gross Profit'].iloc[0])
                data["gpm"] = (latest_gp / latest_revenue) * 100

            if 'Operating Income' in financials.index and latest_revenue and latest_revenue > 0:
                latest_op = float(financials.loc['Operating Income'].iloc[0])
                data["opm"] = (latest_op / latest_revenue) * 100
    except Exception as e:
        logger.debug(f"Failed to fetch YFinance 'financials' for {ticker}: {e}")

    try:
        balance_sheet = stock.balance_sheet
        if not balance_sheet.empty and latest_revenue and latest_revenue > 0:
            receivables = None
            if 'Accounts Receivable' in balance_sheet.index:
                receivables = balance_sheet.loc['Accounts Receivable'].iloc[0]
            elif 'Net Receivables' in balance_sheet.index:
                receivables = balance_sheet.loc['Net Receivables'].iloc[0]
            if receivables is not None and not pd.isna(receivables):
                data["receivables_pct_sales"] = (float(receivables) / latest_revenue) * 100
    except Exception as e:
        logger.debug(f"Failed to fetch YFinance 'balance_sheet' for {ticker}: {e}")
    
    # ── M-SCORE MATH (Bulletproofed Scoping) ──
    if data["sector"] != "Financial Services":
        try:
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            
            # Initialize all variables so they exist regardless of if-statements
            dsri = None; gmi = None; sgi = None; lvgi = None; tata = None
            
            if not financials.empty and not balance_sheet.empty and financials.shape[1] >= 2 and balance_sheet.shape[1] >= 2:
                # DSRI & SGI
                if "Total Revenue" in financials.index:
                    rev_t = financials.loc["Total Revenue"].iloc[0]
                    rev_t1 = financials.loc["Total Revenue"].iloc[1]
                    if rev_t1 > 0:
                        sgi = rev_t / rev_t1
                        
                    rec_t = None
                    rec_t1 = None
                    if "Accounts Receivable" in balance_sheet.index:
                        rec_t = balance_sheet.loc["Accounts Receivable"].iloc[0]
                        rec_t1 = balance_sheet.loc["Accounts Receivable"].iloc[1]
                    elif "Net Receivables" in balance_sheet.index:
                        rec_t = balance_sheet.loc["Net Receivables"].iloc[0]
                        rec_t1 = balance_sheet.loc["Net Receivables"].iloc[1]
                        
                    if rec_t is not None and rec_t1 is not None and rev_t > 0 and rev_t1 > 0:
                        if (rec_t1 / rev_t1) > 0:
                            dsri = (rec_t / rev_t) / (rec_t1 / rev_t1)
                            
                # GMI
                if "Gross Profit" in financials.index and "Total Revenue" in financials.index:
                    gp_t = financials.loc["Gross Profit"].iloc[0]
                    gp_t1 = financials.loc["Gross Profit"].iloc[1]
                    rev_t = financials.loc["Total Revenue"].iloc[0]
                    rev_t1 = financials.loc["Total Revenue"].iloc[1]
                    if rev_t > 0 and rev_t1 > 0 and (gp_t / rev_t) > 0:
                        gmi = (gp_t1 / rev_t1) / (gp_t / rev_t)
                        
                # LVGI
                if "Total Debt" in balance_sheet.index and "Total Assets" in balance_sheet.index:
                    debt_t = balance_sheet.loc["Total Debt"].iloc[0]
                    debt_t1 = balance_sheet.loc["Total Debt"].iloc[1]
                    assets_t = balance_sheet.loc["Total Assets"].iloc[0]
                    assets_t1 = balance_sheet.loc["Total Assets"].iloc[1]
                    if assets_t > 0 and assets_t1 > 0 and debt_t1 > 0:
                        lvgi = (debt_t / assets_t) / (debt_t1 / assets_t1)
                        
                # TATA (Accruals)
                if "Net Income" in financials.index and "Total Assets" in balance_sheet.index:
                    ni_t = financials.loc["Net Income"].iloc[0]
                    assets_t = balance_sheet.loc["Total Assets"].iloc[0]
                    cashflow = stock.cashflow
                    if not cashflow.empty and "Operating Cash Flow" in cashflow.index:
                        ocf_t = cashflow.loc["Operating Cash Flow"].iloc[0]
                        if assets_t > 0:
                            tata = (ni_t - ocf_t) / assets_t

            data["m_score_components"] = {
                "dsri": dsri, "gmi": gmi, "sgi": sgi, "lvgi": lvgi, "tata": tata
            }
        except Exception as e:
            logger.debug(f"[{ticker}] M-Score components skipped/failed: {e}")

    return data