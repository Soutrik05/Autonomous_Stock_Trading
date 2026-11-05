"""
Unit tests for Zerodha Varsity Module 3 (DCF Intrinsic Value Band) and Module 9 (Kelly Sizing):
- Sector-banded discount rates and exhaustion
- Bounded CapEx-intensity ratio FCFF_0
- Multi-period trailing PAT growth clamp [0.0%, 15.0%]
- Primary (Market Cap / Price) vs Fallback (PAT / EPS) shares count derivation
- EV-to-Equity bridge and per-share intrinsic value
- Dynamic nightly dcf_discount_pct in FeatureSnapshot
- Kelly-Criterion empirical sizing helper
- Varsity persona hurdles and metric integration
"""
import sqlite3
import pytest
import pandas as pd
from unittest.mock import MagicMock

from ingestion.sync_fundamentals import (
    SECTOR_DISCOUNT_RATES,
    get_sector_discount_rate,
    compute_dcf_intrinsic_value,
    parse_fundamental_metrics,
)
from features.builder import compute_snapshot_features
from agents.context_assembler import compute_kelly_recommendation, build_portfolio_state_block
from agents.personas.varsity import VARSITY, VARSITY_FUNDAMENTAL_HURDLES, VARSITY_EXTRA_METRICS
from watchlist.watchlist_refresh import stage2_sort


class TestSectorDiscountRates:
    def test_defensive_sectors_have_11_pct_rate(self):
        for sec in ["Fast Moving Consumer Goods", "Healthcare", "Information Technology"]:
            assert get_sector_discount_rate(sec) == 0.11

    def test_cyclical_sectors_have_13_5_pct_rate(self):
        cyclicals = [
            "Metals & Mining", "Realty", "Construction", "Capital Goods",
            "Power", "Telecommunication", "Oil Gas & Consumable Fuels", "Construction Materials"
        ]
        for sec in cyclicals:
            assert get_sector_discount_rate(sec) == 0.135

    def test_general_sectors_have_12_pct_rate(self):
        generals = [
            "Automobile and Auto Components", "Chemicals", "Consumer Durables",
            "Consumer Services", "Services", "Textiles", "Media Entertainment & Publication", "Diversified"
        ]
        for sec in generals:
            assert get_sector_discount_rate(sec) == 0.12

    def test_financial_services_returns_none(self):
        for sec in ["Financial Services", "financials", "Banking", "Banks", "NBFC"]:
            assert get_sector_discount_rate(sec) is None

    def test_unmapped_or_empty_sector_defaults_to_12_pct(self):
        assert get_sector_discount_rate("Aerospace & Defense") == 0.12
        assert get_sector_discount_rate(None) == 0.12
        assert get_sector_discount_rate("") == 0.12


class TestDCFIntrinsicValueMath:
    def test_standard_dcf_calculation(self):
        # 10,000 Cr CFO, -3,000 Cr CFI (30% capex) -> FCFF_0 = 7,000 Cr
        # Growth 8%, Discount 11% (IT), 100 Cr shares
        # Cash = 2,000 Cr, Liabilities = 1,000 Cr
        iv = compute_dcf_intrinsic_value(
            cfo=10000.0,
            cfi=-3000.0,
            cash_end=2000.0,
            curr_liab=600.0,
            non_curr_liab=400.0,
            growth_rate=0.08,
            discount_rate=0.11,
            shares_outstanding=1000000000,  # 100 Cr shares
        )
        assert iv is not None
        assert iv > 0
        # In ₹ per share, roughly between 1,000 and 2,000
        assert 1000.0 <= iv <= 2500.0

    def test_bounded_capex_clamp_upper(self):
        # CFI = -8,000 Cr on 10,000 Cr CFO -> ratio = 0.80, clamped to 0.50
        iv_clamped = compute_dcf_intrinsic_value(
            cfo=10000.0,
            cfi=-8000.0,
            cash_end=1000.0,
            curr_liab=500.0,
            non_curr_liab=500.0,
            growth_rate=0.05,
            discount_rate=0.12,
            shares_outstanding=500000000,
        )
        # Should match exact 50% deduction (FCFF_0 = 5,000 Cr)
        iv_50pct = compute_dcf_intrinsic_value(
            cfo=10000.0,
            cfi=-5000.0,
            cash_end=1000.0,
            curr_liab=500.0,
            non_curr_liab=500.0,
            growth_rate=0.05,
            discount_rate=0.12,
            shares_outstanding=500000000,
        )
        assert iv_clamped == iv_50pct

    def test_bounded_capex_clamp_lower(self):
        # CFI = -200 Cr on 10,000 Cr CFO -> ratio = 0.02, clamped to 0.10
        iv_clamped = compute_dcf_intrinsic_value(
            cfo=10000.0,
            cfi=-200.0,
            cash_end=1000.0,
            curr_liab=500.0,
            non_curr_liab=500.0,
            growth_rate=0.05,
            discount_rate=0.12,
            shares_outstanding=500000000,
        )
        iv_10pct = compute_dcf_intrinsic_value(
            cfo=10000.0,
            cfi=-1000.0,
            cash_end=1000.0,
            curr_liab=500.0,
            non_curr_liab=500.0,
            growth_rate=0.05,
            discount_rate=0.12,
            shares_outstanding=500000000,
        )
        assert iv_clamped == iv_10pct

    def test_growth_floor_clamped_to_zero_for_declining_business(self):
        # Growth of -20% should be clamped to 0.0% (flat cash flows), not positive 5%
        iv_neg = compute_dcf_intrinsic_value(
            cfo=5000.0,
            cfi=-1500.0,
            cash_end=500.0,
            curr_liab=200.0,
            non_curr_liab=300.0,
            growth_rate=-0.20,
            discount_rate=0.12,
            shares_outstanding=200000000,
        )
        iv_zero = compute_dcf_intrinsic_value(
            cfo=5000.0,
            cfi=-1500.0,
            cash_end=500.0,
            curr_liab=200.0,
            non_curr_liab=300.0,
            growth_rate=0.0,
            discount_rate=0.12,
            shares_outstanding=200000000,
        )
        assert iv_neg == iv_zero

    def test_negative_cfo_returns_none(self):
        assert compute_dcf_intrinsic_value(
            cfo=-500.0,
            cfi=-100.0,
            cash_end=100.0,
            curr_liab=100.0,
            non_curr_liab=100.0,
            growth_rate=0.05,
            discount_rate=0.12,
            shares_outstanding=1000000,
        ) is None

    def test_financial_services_sector_returns_none(self):
        rate = get_sector_discount_rate("Financial Services")
        assert compute_dcf_intrinsic_value(
            cfo=5000.0,
            cfi=-500.0,
            cash_end=1000.0,
            curr_liab=500.0,
            non_curr_liab=500.0,
            growth_rate=0.05,
            discount_rate=rate,  # None
            shares_outstanding=10000000,
        ) is None


class TestSharesCountDerivationPriority:
    def test_primary_market_cap_and_price_used(self):
        # Market Cap = 20,000 Cr, Price = Rs 500 -> Shares = 40 Cr = 400,000,000
        # PAT = 1,000 Cr, EPS = 10 -> Shares by fallback would be 100 Cr = 1,000,000,000
        key_ratios = [{"name": "Market Cap", "company_value": 20000.0}]
        inc_stmt = {
            "income_statement": [{"category": "net_profit", "history": [{"change": 10.0}]}],
            "full_statement": [
                {"category": "Profit After Tax", "history": [{"amount": 1000.0}]},
                {"category": "EPS - Basic", "history": [{"amount": 10.0}]},
            ],
        }
        res = parse_fundamental_metrics(
            ticker="ABC",
            as_of_date="2026-10-30",
            key_ratios=key_ratios,
            income_stmt=inc_stmt,
            balance_sheet={"full_statement": []},
            cash_flow={"full_statement": [{"category": "Cash flow from Operations", "history": [{"amount": 1500.0}]}]},
            share_holdings=[],
            sector="Services",
            current_price=500.0,
        )
        assert res["dcf_iv_share"] is not None
        # With 40 Cr shares (market cap / price), IV should be 2.5x higher than with 100 Cr shares
        # Verify it used 40 Cr shares by recomputing
        expected_iv = compute_dcf_intrinsic_value(
            cfo=1500.0,
            cfi=None,
            cash_end=0.0,
            curr_liab=0.0,
            non_curr_liab=0.0,
            growth_rate=0.10,
            discount_rate=0.12,
            shares_outstanding=400000000,
        )
        assert res["dcf_iv_share"] == expected_iv

    def test_fallback_pat_and_eps_used_when_market_cap_missing(self):
        # Market Cap missing from key_ratios, fallback to PAT=2000 Cr / EPS=50 -> 40 Cr shares
        key_ratios = [{"name": "P/E", "company_value": 20.0}]
        inc_stmt = {
            "income_statement": [{"category": "net_profit", "history": [{"change": 8.0}]}],
            "full_statement": [
                {"category": "Profit After Tax", "history": [{"amount": 2000.0}]},
                {"category": "EPS - Basic", "history": [{"amount": 50.0}]},
            ],
        }
        res = parse_fundamental_metrics(
            ticker="XYZ",
            as_of_date="2026-10-30",
            key_ratios=key_ratios,
            income_stmt=inc_stmt,
            balance_sheet={"full_statement": []},
            cash_flow={"full_statement": [{"category": "Cash flow from Operations", "history": [{"amount": 2200.0}]}]},
            share_holdings=[],
            sector="Healthcare",
            current_price=1000.0,
        )
        assert res["dcf_iv_share"] is not None
        expected_iv = compute_dcf_intrinsic_value(
            cfo=2200.0,
            cfi=None,
            cash_end=0.0,
            curr_liab=0.0,
            non_curr_liab=0.0,
            growth_rate=0.08,
            discount_rate=0.11,
            shares_outstanding=400000000,
        )
        assert res["dcf_iv_share"] == expected_iv


class TestDynamicNightlyDCFDiscount:
    def test_dcf_discount_pct_derived_from_tonight_close(self):
        df = pd.DataFrame({
            "trade_date": ["2026-10-30"],
            "open": [1000.0],
            "high": [1020.0],
            "low": [990.0],
            "close": [1000.0],
            "volume": [500000],
        })
        # If IV is Rs 1200 and Close is Rs 1000 -> discount = (1200 - 1000) / 1000 * 100 = +20.0%
        fundamental_row = {"dcf_iv_share": 1200.0, "roce_pct": 18.0}
        features = compute_snapshot_features(
            df=df,
            india_vix=14.0,
            regime="LOW_VOL",
            fundamental_row=fundamental_row,
        )
        assert features["dcf_discount_pct"] == 20.0

    def test_dcf_discount_pct_is_none_for_missing_iv(self):
        df = pd.DataFrame({
            "trade_date": ["2026-10-30"],
            "open": [500.0],
            "high": [510.0],
            "low": [495.0],
            "close": [500.0],
            "volume": [100000],
        })
        fundamental_row = {"dcf_iv_share": None, "roce_pct": 14.0}
        features = compute_snapshot_features(
            df=df,
            india_vix=14.0,
            regime="LOW_VOL",
            fundamental_row=fundamental_row,
        )
        assert features["dcf_discount_pct"] is None


class TestKellyRecommendation:
    def test_insufficient_closed_trades_returns_trade_count(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE positions (agent_id TEXT, status TEXT, realized_pnl_pct REAL)")
        # Insert only 5 closed trades
        for p in [5.0, -3.0, 8.0, -2.0, 4.0]:
            conn.execute("INSERT INTO positions VALUES ('varsity', 'CLOSED', ?)", (p,))
        res = compute_kelly_recommendation(conn, "varsity")
        assert res["trades"] == 5
        assert "recommended_risk_pct" not in res

    def test_sufficient_closed_trades_calculates_half_kelly(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE positions (agent_id TEXT, status TEXT, realized_pnl_pct REAL)")
        # 12 closed trades: 8 wins (+6.0% each), 4 losses (-3.0% each)
        # Win rate W = 8/12 = 0.667, Avg win = 6.0, Avg loss = 3.0 -> R = 2.0
        # Kelly = 0.667 - (0.333 / 2.0) = 0.667 - 0.167 = 0.50 (50%)
        # Half Kelly = 25% -> clamped to max 2.0% capital risk budget
        for _ in range(8):
            conn.execute("INSERT INTO positions VALUES ('varsity', 'CLOSED', 6.0)")
        for _ in range(4):
            conn.execute("INSERT INTO positions VALUES ('varsity', 'CLOSED', -3.0)")
        res = compute_kelly_recommendation(conn, "varsity")
        assert res["trades"] == 12
        assert res["win_rate"] == 66.7
        assert res["payoff_ratio"] == 2.0
        assert res["recommended_risk_pct"] == 2.0  # capped at 2.0%


class TestVarsityWatchlistRankingAndHurdles:
    def test_roe_pct_in_fundamental_hurdles(self):
        hurdles = VARSITY_FUNDAMENTAL_HURDLES["all"]
        features_checked = [h["feature"] for h in hurdles]
        assert "roce_pct" in features_checked
        assert "roe_pct" in features_checked
        assert "debt_to_equity" in features_checked

    def test_dcf_discount_pct_in_extra_metrics(self):
        assert "dcf_discount_pct" in VARSITY_EXTRA_METRICS

    def test_varsity_stage2_percentile_composite_with_dcf(self):
        # 3 candidates: T1 has high DCF discount (+25%), T2 has negative discount (-10%), T3 has None (Financial)
        candidates = ["T1", "T2", "T3"]
        features_by_ticker = {
            "T1": {"volume_surge": 1.5, "rsi_14": 55.0, "roce_pct": 18.0, "debt_to_equity": 0.5, "dcf_discount_pct": 25.0},
            "T2": {"volume_surge": 1.2, "rsi_14": 52.0, "roce_pct": 14.0, "debt_to_equity": 0.8, "dcf_discount_pct": -10.0},
            "T3": {"volume_surge": 1.4, "rsi_14": 54.0, "roce_pct": 16.0, "debt_to_equity": 0.6, "dcf_discount_pct": None},
        }
        sector_by_ticker = {"T1": "IT", "T2": "Metals", "T3": "Financial Services"}
        scored = stage2_sort(candidates, features_by_ticker, sector_by_ticker, VARSITY)
        assert len(scored) == 3
        # T1 has superior metrics and DCF discount, should be ranked 1st
        assert scored[0]["ticker"] == "T1"
        # T3 with None DCF should receive neutral 0.50 percentile rank without error
        assert any(s["ticker"] == "T3" for s in scored)

