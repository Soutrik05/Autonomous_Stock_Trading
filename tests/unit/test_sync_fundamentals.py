"""
Unit tests for ingestion/sync_fundamentals.py and its integration with core/build_features.py.
Tests ratio parsing, derived metric formulas, 14-day cadence check, API error resilience,
and feature snapshot ingestion.
"""

import json
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from core.clock import FakeClock
from features.builder import compute_snapshot_features
from features.builder import run as run_build_features
from ingestion.sync_fundamentals import (
    ensure_schema,
    is_sync_due,
    parse_fundamental_metrics,
    sync_ticker,
)
from ingestion.sync_fundamentals import (
    run as run_sync_fundamentals,
)
from ingestion.upstox_client import UpstoxAPIError

# -----------------------------------------------------------------------------
# Fixtures & Sample Payloads
# -----------------------------------------------------------------------------

SAMPLE_KEY_RATIOS = [
    {"name": "P/E", "company_value": 24.50},
    {"name": "P/B", "company_value": 3.80},
    {"name": "ROCE", "company_value": 18.25},
    {"name": "ROE", "company_value": 16.40},
]

SAMPLE_INCOME_STMT = {
    "income_statement": [
        {
            "category": "net_profit",
            "history": [
                {"period": "2025", "value": 1500.0, "change": 20.0},
                {"period": "2024", "value": 1250.0, "change": 15.0},
            ],
        },
        {
            "category": "revenue",
            "history": [
                {"period": "2025", "value": 10000.0, "change": 12.5},
                {"period": "2024", "value": 8888.0, "change": 10.0},
            ],
        },
    ],
    "full_statement": [
        {
            "particular": "Profit After Tax",
            "history": [{"period": "2025", "value": 1500.0}],
        }
    ],
}

SAMPLE_BALANCE_SHEET = {
    "full_statement": [
        {
            "particular": "Equity Capital",
            "history": [{"period": "2025", "value": 2000.0}],
        },
        {
            "particular": "Current Liabilities",
            "history": [{"period": "2025", "value": 600.0}],
        },
        {
            "particular": "Non-Current Liabilities",
            "history": [{"period": "2025", "value": 400.0}],
        },
    ]
}

SAMPLE_CASH_FLOW = {
    "full_statement": [
        {
            "particular": "Cash flow from Operations",
            "history": [{"period": "2025", "value": 1800.0}],
        }
    ]
}

SAMPLE_SHARE_HOLDINGS = [
    {
        "category": "promoters",
        "history": [{"period": "2025-03", "value": 52.4}],
    },
    {
        "category": "fii",
        "history": [{"period": "2025-03", "value": 18.6}],
    },
    {
        "category": "mutual_funds",
        "history": [{"period": "2025-03", "value": 8.0}],
    },
    {
        "category": "other_dii",
        "history": [{"period": "2025-03", "value": 6.5}],
    },
]


@pytest.fixture
def fundamental_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def portfolio_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE symbols (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            isin TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE pipeline_runs (
            job TEXT NOT NULL,
            run_date TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            detail TEXT,
            PRIMARY KEY (job, run_date)
        );
        CREATE TABLE feature_snapshots (
            ticker TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            features_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (ticker, as_of_date, schema_version)
        );
        """
    )
    yield conn
    conn.close()


@pytest.fixture
def ohlcv_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE ohlcv (
            ticker TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (ticker, trade_date)
        );
        CREATE TABLE ticker_status (
            ticker TEXT PRIMARY KEY,
            status TEXT NOT NULL
        );
        """
    )
    yield conn
    conn.close()


@pytest.fixture
def macro_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE macro_daily (
            trade_date TEXT PRIMARY KEY,
            market_closed INTEGER NOT NULL,
            india_vix REAL,
            regime TEXT NOT NULL
        );
        """
    )
    yield conn
    conn.close()


# -----------------------------------------------------------------------------
# 1. Parsing & Derived Metrics Tests
# -----------------------------------------------------------------------------


class TestParseFundamentalMetrics:
    def test_full_payload_all_metrics_extracted(self):
        res = parse_fundamental_metrics(
            ticker="INFY",
            as_of_date="2025-06-01",
            key_ratios=SAMPLE_KEY_RATIOS,
            income_stmt=SAMPLE_INCOME_STMT,
            balance_sheet=SAMPLE_BALANCE_SHEET,
            cash_flow=SAMPLE_CASH_FLOW,
            share_holdings=SAMPLE_SHARE_HOLDINGS,
        )

        assert res["ticker"] == "INFY"
        assert res["as_of_date"] == "2025-06-01"
        assert res["pe"] == 24.50
        assert res["pb"] == 3.80
        assert res["roce_pct"] == 18.25
        assert res["roe_pct"] == 16.40

        # pat_growth_yoy_pct = 20.0, peg = 24.5 / 20.0 = 1.225
        assert res["pat_growth_yoy_pct"] == 20.0
        assert res["revenue_growth_yoy_pct"] == 12.5
        assert res["peg"] == 1.225

        # debt_to_equity = (600 + 400) / 2000 = 0.50
        assert res["debt_to_equity"] == 0.50

        # cfo_to_pat = 1800 / 1500 = 1.20
        assert res["cfo_to_pat"] == 1.20

        # shareholdings
        assert res["promoter_holding_pct"] == 52.4
        assert res["fii_holding_pct"] == 18.6
        # dii = mutual_funds (8.0) + other_dii (6.5) = 14.5
        assert res["dii_holding_pct"] == 14.5
        assert res["raw_json"] is not None

    def test_peg_calculation_zero_or_negative_pat_growth(self):
        income_stmt_neg = {
            "income_statement": [
                {
                    "category": "net_profit",
                    "history": [{"period": "2025", "value": 800.0, "change": -10.5}],
                }
            ],
            "full_statement": [],
        }
        res = parse_fundamental_metrics(
            ticker="TATASTEEL",
            as_of_date="2025-06-01",
            key_ratios=SAMPLE_KEY_RATIOS,
            income_stmt=income_stmt_neg,
            balance_sheet=SAMPLE_BALANCE_SHEET,
            cash_flow=SAMPLE_CASH_FLOW,
            share_holdings=SAMPLE_SHARE_HOLDINGS,
        )
        assert res["pat_growth_yoy_pct"] == -10.5
        assert res["peg"] is None

    def test_debt_to_equity_zero_or_negative_equity(self):
        bs_zero_equity = {
            "full_statement": [
                {"particular": "Equity Capital", "history": [{"period": "2025", "value": 0.0}]},
                {"particular": "Current Liabilities", "history": [{"period": "2025", "value": 500.0}]},
            ]
        }
        res = parse_fundamental_metrics(
            ticker="DISTRESSED",
            as_of_date="2025-06-01",
            key_ratios=[],
            income_stmt={"income_statement": [], "full_statement": []},
            balance_sheet=bs_zero_equity,
            cash_flow={"full_statement": []},
            share_holdings=[],
        )
        assert res["debt_to_equity"] is None

    def test_cfo_to_pat_zero_or_negative_pat(self):
        inc_zero_pat = {
            "income_statement": [],
            "full_statement": [{"particular": "Profit After Tax", "history": [{"period": "2025", "value": 0.0}]}],
        }
        res = parse_fundamental_metrics(
            ticker="LOSSMAKER",
            as_of_date="2025-06-01",
            key_ratios=[],
            income_stmt=inc_zero_pat,
            balance_sheet={"full_statement": []},
            cash_flow=SAMPLE_CASH_FLOW,
            share_holdings=[],
        )
        assert res["cfo_to_pat"] is None


# -----------------------------------------------------------------------------
# 2. 14-Day Cadence Tests
# -----------------------------------------------------------------------------


class TestSyncDueCadence:
    def test_unseen_ticker_is_due(self, fundamental_conn):
        assert is_sync_due(fundamental_conn, "NEWCO", "2025-06-15") is True

    def test_fresh_ticker_under_14_days_is_not_due(self, fundamental_conn):
        fundamental_conn.execute(
            """
            INSERT INTO fundamental_sync_status (ticker, isin, last_synced_at, status)
            VALUES ('TCS', 'INE467B01029', '2025-06-10T10:00:00', 'SUCCESS')
            """
        )
        # 5 days later: not due
        assert is_sync_due(fundamental_conn, "TCS", "2025-06-15", cadence_days=14) is False

    def test_stale_ticker_over_14_days_is_due(self, fundamental_conn):
        fundamental_conn.execute(
            """
            INSERT INTO fundamental_sync_status (ticker, isin, last_synced_at, status)
            VALUES ('TCS', 'INE467B01029', '2025-05-30T10:00:00', 'SUCCESS')
            """
        )
        # 16 days later: due
        assert is_sync_due(fundamental_conn, "TCS", "2025-06-15", cadence_days=14) is True

    def test_failed_status_is_due_immediately(self, fundamental_conn):
        fundamental_conn.execute(
            """
            INSERT INTO fundamental_sync_status (ticker, isin, last_synced_at, status)
            VALUES ('TCS', 'INE467B01029', '2025-06-15T09:00:00', 'FAILED')
            """
        )
        # Even same day, FAILED status should be retried
        assert is_sync_due(fundamental_conn, "TCS", "2025-06-15", cadence_days=14) is True

    def test_force_flag_bypasses_cadence(self, fundamental_conn):
        fundamental_conn.execute(
            """
            INSERT INTO fundamental_sync_status (ticker, isin, last_synced_at, status)
            VALUES ('TCS', 'INE467B01029', '2025-06-15T09:00:00', 'SUCCESS')
            """
        )
        assert is_sync_due(fundamental_conn, "TCS", "2025-06-15", cadence_days=14, force=True) is True


# -----------------------------------------------------------------------------
# 3. sync_ticker Unit Tests
# -----------------------------------------------------------------------------


class TestSyncTicker:
    def test_sync_ticker_success(self, fundamental_conn):
        mock_client = MagicMock()
        mock_client.get_key_ratios.return_value = SAMPLE_KEY_RATIOS
        mock_client.get_income_statement.return_value = SAMPLE_INCOME_STMT
        mock_client.get_balance_sheet.return_value = SAMPLE_BALANCE_SHEET
        mock_client.get_cash_flow.return_value = SAMPLE_CASH_FLOW
        mock_client.get_share_holdings.return_value = SAMPLE_SHARE_HOLDINGS

        clock = FakeClock(datetime(2025, 6, 15, 10, 0, 0))
        success = sync_ticker(
            fundamental_conn=fundamental_conn,
            client=mock_client,
            ticker="INFY",
            isin="INE009A01021",
            as_of_date="2025-06-15",
            clock=clock,
        )
        assert success is True

        # Check fundamental_sync_status
        status_row = fundamental_conn.execute("SELECT * FROM fundamental_sync_status WHERE ticker = 'INFY'").fetchone()
        assert status_row is not None
        assert status_row["status"] == "SUCCESS"
        assert status_row["isin"] == "INE009A01021"

        # Check fundamental_ratios
        ratio_row = fundamental_conn.execute("SELECT * FROM fundamental_ratios WHERE ticker = 'INFY'").fetchone()
        assert ratio_row is not None
        assert ratio_row["pe"] == 24.50
        assert ratio_row["roce_pct"] == 18.25
        assert ratio_row["debt_to_equity"] == 0.50

    def test_sync_ticker_api_failure(self, fundamental_conn):
        mock_client = MagicMock()
        mock_client.get_key_ratios.side_effect = UpstoxAPIError("API down 503")

        clock = FakeClock(datetime(2025, 6, 15, 10, 0, 0))
        success = sync_ticker(
            fundamental_conn=fundamental_conn,
            client=mock_client,
            ticker="BADCO",
            isin="INE999X01010",
            as_of_date="2025-06-15",
            clock=clock,
        )
        assert success is False

        status_row = fundamental_conn.execute("SELECT * FROM fundamental_sync_status WHERE ticker = 'BADCO'").fetchone()
        assert status_row is not None
        assert status_row["status"] == "FAILED"

        # No ratios written on failure
        ratio_row = fundamental_conn.execute("SELECT * FROM fundamental_ratios WHERE ticker = 'BADCO'").fetchone()
        assert ratio_row is None

    def test_sync_ticker_persists_corporate_actions(self, fundamental_conn):
        mock_client = MagicMock()
        mock_client.get_key_ratios.return_value = SAMPLE_KEY_RATIOS
        mock_client.get_income_statement.return_value = SAMPLE_INCOME_STMT
        mock_client.get_balance_sheet.return_value = SAMPLE_BALANCE_SHEET
        mock_client.get_cash_flow.return_value = SAMPLE_CASH_FLOW
        mock_client.get_share_holdings.return_value = SAMPLE_SHARE_HOLDINGS
        mock_client.get_corporate_actions.return_value = [
            {
                "name": "Dividend",
                "expiry_date": "2025-07-01",
                "amount": 10.0,
                "ratio": None,
                "event_details": [{"name": "Dividend %", "value": "100%"}],
            },
            {
                "name": "Split",
                "expiry_date": "2025-08-15",
                "amount": None,
                "ratio": "1:2",
                "event_details": [],
            },
        ]

        clock = FakeClock(datetime(2025, 6, 15, 10, 0, 0))
        success = sync_ticker(
            fundamental_conn=fundamental_conn,
            client=mock_client,
            ticker="INFY",
            isin="INE009A01021",
            as_of_date="2025-06-15",
            clock=clock,
        )
        assert success is True

        rows = fundamental_conn.execute(
            "SELECT * FROM corporate_actions WHERE ticker = 'INFY' ORDER BY action_type"
        ).fetchall()
        assert len(rows) == 2
        div_row = [r for r in rows if r["action_type"] == "Dividend"][0]
        assert div_row["amount"] == 10.0
        assert div_row["expiry_date"] == "2025-07-01"

        split_row = [r for r in rows if r["action_type"] == "Split"][0]
        assert split_row["ratio"] == "1:2"
        assert split_row["expiry_date"] == "2025-08-15"


# -----------------------------------------------------------------------------
# 4. run() Pipeline Tests
# -----------------------------------------------------------------------------


class TestRunPipeline:
    def test_run_syncs_active_and_skips_fresh(self, portfolio_conn, fundamental_conn):
        # Insert 2 active symbols and 1 inactive symbol
        portfolio_conn.executemany(
            "INSERT INTO symbols (ticker, isin, is_active) VALUES (?, ?, ?)",
            [
                ("INFY", "INE009A01021", 1),
                ("TCS", "INE467B01029", 1),
                ("OLDCO", "INE000000000", 0),
            ],
        )

        # TCS is already fresh (synced 3 days ago)
        fundamental_conn.execute(
            """
            INSERT INTO fundamental_sync_status (ticker, isin, last_synced_at, status)
            VALUES ('TCS', 'INE467B01029', '2025-06-12T10:00:00', 'SUCCESS')
            """
        )

        mock_client = MagicMock()
        mock_client.get_key_ratios.return_value = SAMPLE_KEY_RATIOS
        mock_client.get_income_statement.return_value = SAMPLE_INCOME_STMT
        mock_client.get_balance_sheet.return_value = SAMPLE_BALANCE_SHEET
        mock_client.get_cash_flow.return_value = SAMPLE_CASH_FLOW
        mock_client.get_share_holdings.return_value = SAMPLE_SHARE_HOLDINGS

        clock = FakeClock(datetime(2025, 6, 15, 18, 0, 0))

        summary = run_sync_fundamentals(
            as_of_date="2025-06-15",
            clock=clock,
            portfolio_conn=portfolio_conn,
            fundamental_conn=fundamental_conn,
            client=mock_client,
        )

        assert summary["status"] == "SUCCESS"
        assert summary["checked"] == 2
        assert summary["synced"] == 1  # INFY synced
        assert summary["skipped_fresh"] == 1  # TCS skipped
        assert summary["failed"] == 0

        # Verify pipeline_runs in portfolio_conn
        run_row = portfolio_conn.execute(
            "SELECT * FROM pipeline_runs WHERE job = 'sync_fundamentals' AND run_date = '2025-06-15'"
        ).fetchone()
        assert run_row is not None
        assert run_row["status"] == "SUCCESS"


# -----------------------------------------------------------------------------
# 5. Integration with core/build_features.py
# -----------------------------------------------------------------------------


class TestBuildFeaturesFundamentalIntegration:
    def test_compute_snapshot_features_with_fundamental_row(self):
        # 200 sessions of dummy OHLCV
        df = pd.DataFrame(
            {
                "trade_date": [f"2025-01-{i + 1:02d}" for i in range(200)],
                "open": [100.0] * 200,
                "high": [105.0] * 200,
                "low": [95.0] * 200,
                "close": [102.0] * 200,
                "volume": [100000.0] * 200,
            }
        )

        fundamental_row = {
            "roce_pct": 22.5,
            "roe_pct": 19.8,
            "pe": 15.2,
            "pb": 2.8,
            "peg": 0.85,
            "debt_to_equity": 0.35,
            "cfo_to_pat": 1.15,
            "pat_growth_yoy_pct": 17.8,
            "revenue_growth_yoy_pct": 14.0,
            "promoter_holding_pct": 65.2,
        }

        features = compute_snapshot_features(
            df=df,
            india_vix=13.5,
            regime="BULL_QUIET",
            fundamental_row=fundamental_row,
        )

        # Technical & macro check
        assert features["close"] == 102.0
        assert features["india_vix"] == 13.5
        assert features["regime"] == "BULL_QUIET"

        # Fundamental check
        assert features["roce_pct"] == 22.5
        assert features["roe_pct"] == 19.8
        assert features["pe"] == 15.2
        assert features["pb"] == 2.8
        assert features["peg"] == 0.85
        assert features["debt_to_equity"] == 0.35
        assert features["cfo_to_pat"] == 1.15
        assert features["pat_growth_yoy_pct"] == 17.8
        assert features["revenue_growth_yoy_pct"] == 14.0
        assert features["promoter_holding_pct"] == 65.2

        # Features not in fundamental_row remain None
        assert features["interest_coverage"] is None
        assert features["promoter_pledge_pct"] is None

    def test_run_build_features_merges_fundamental_db_into_snapshots(
        self, portfolio_conn, ohlcv_conn, macro_conn, fundamental_conn
    ):
        as_of_date = "2025-06-15"
        clock = FakeClock(datetime(2025, 6, 15, 18, 0, 0))

        # 1. Active symbol
        portfolio_conn.execute("INSERT INTO symbols (ticker, isin, is_active) VALUES ('INFY', 'INE009A01021', 1)")
        # Ingestion marked SUCCESS
        portfolio_conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at) "
            "VALUES ('ingestion', ?, 'SUCCESS', ?, ?)",
            (as_of_date, clock.now_iso(), clock.now_iso()),
        )

        # 2. OHLCV data for 200 sessions ending on as_of_date
        dates = pd.date_range(end=as_of_date, periods=200, freq="B").strftime("%Y-%m-%d").tolist()
        ohlcv_rows = [("INFY", d, 100.0, 105.0, 95.0, 101.0, 50000.0) for d in dates]
        ohlcv_conn.executemany(
            "INSERT INTO ohlcv (ticker, trade_date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ohlcv_rows,
        )

        # 3. Macro row
        macro_conn.execute(
            "INSERT INTO macro_daily (trade_date, market_closed, india_vix, regime) VALUES (?, 0, 14.2, 'BULL_QUIET')",
            (as_of_date,),
        )

        # 4. Fundamental row
        fundamental_conn.execute(
            """
            INSERT INTO fundamental_ratios (
                ticker, as_of_date, pe, pb, roce_pct, roe_pct, peg, debt_to_equity,
                cfo_to_pat, pat_growth_yoy_pct, revenue_growth_yoy_pct, promoter_holding_pct,
                updated_at
            ) VALUES (?, ?, 25.0, 4.0, 20.0, 18.0, 1.25, 0.45, 1.10, 20.0, 15.0, 51.5, ?)
            """,
            ("INFY", as_of_date, clock.now_iso()),
        )

        # 5. Run build_features
        res = run_build_features(
            as_of_date=as_of_date,
            clock=clock,
            portfolio_conn=portfolio_conn,
            ohlcv_conn=ohlcv_conn,
            macro_conn=macro_conn,
            fundamental_conn=fundamental_conn,
        )

        assert res["status"] == "SUCCESS"
        assert res["written"] == 1

        # 6. Verify feature snapshot has fundamental metrics
        snap_row = portfolio_conn.execute(
            "SELECT features_json FROM feature_snapshots WHERE ticker = 'INFY' AND as_of_date = ?",
            (as_of_date,),
        ).fetchone()
        assert snap_row is not None
        features = json.loads(snap_row["features_json"])

        assert features["pe"] == 25.0
        assert features["roce_pct"] == 20.0
        assert features["peg"] == 1.25
        assert features["debt_to_equity"] == 0.45
        assert features["promoter_holding_pct"] == 51.5
