"""
Unit tests for reflection/forensics.py.

Strategy:
  - All three SQLite connections (portfolio, ohlcv, macro) are in-memory.
  - A helper seeds the minimum required schema rows (positions, ohlcv, macro_daily,
    feature_snapshots).
  - One test per classification branch; tests are deterministic and offline.

See Plan_v3 section 5.2.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta

import pytest

import learning.forensics as forensics
from ingestion.sync_macro import ensure_schema as ensure_macro_schema
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _portfolio_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS positions (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id               TEXT NOT NULL,
            ticker                 TEXT NOT NULL,
            sector                 TEXT NOT NULL DEFAULT 'IT',
            shares                 INTEGER NOT NULL DEFAULT 10,
            avg_entry_price_paise  INTEGER NOT NULL,
            stop_paise             INTEGER NOT NULL DEFAULT 0,
            target_paise           INTEGER NOT NULL DEFAULT 0,
            last_price_paise       INTEGER NOT NULL DEFAULT 0,
            status                 TEXT NOT NULL DEFAULT 'CLOSED',
            entry_date             TEXT NOT NULL,
            exit_date              TEXT NOT NULL,
            exit_reason            TEXT,
            hold_days              INTEGER,
            realized_pnl_paise     INTEGER,
            realized_pnl_pct       REAL,
            forensics_type         TEXT,
            regime_at_exit         TEXT,
            diagnosis_json         TEXT
        );
        CREATE TABLE IF NOT EXISTS feature_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT NOT NULL,
            as_of_date      TEXT NOT NULL,
            schema_version  INTEGER NOT NULL DEFAULT 1,
            features_json   TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT '2025-01-01T00:00:00'
        );
    """)
    return conn


def _ohlcv_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    return conn


def _macro_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    ensure_macro_schema(conn)
    return conn


def _insert_position(
    conn: sqlite3.Connection,
    agent_id: str = "agent-simons",
    ticker: str = "RELIANCE",
    entry_price_paise: int = 100_00_00,  # Rs 10000
    exit_reason: str = "STOP_HIT",
    hold_days: int = 5,
    pnl_pct: float = -3.0,
    entry_date: str = "2025-01-01",
    exit_date: str = "2025-01-08",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO positions
            (agent_id, ticker, sector, shares, avg_entry_price_paise,
             stop_paise, target_paise, last_price_paise,
             status, entry_date, exit_date, exit_reason,
             hold_days, realized_pnl_paise, realized_pnl_pct)
        VALUES (?, ?, 'IT', 10, ?,
                0, 0, 0,
                'CLOSED', ?, ?, ?,
                ?, ?, ?)
        """,
        (
            agent_id,
            ticker,
            entry_price_paise,
            entry_date,
            exit_date,
            exit_reason,
            hold_days,
            int(entry_price_paise * pnl_pct / 100),
            pnl_pct,
        ),
    )
    return cur.lastrowid


def _add_ohlcv(
    conn: sqlite3.Connection,
    ticker: str,
    start_date: str,
    days: int,
    open_: float = 100.0,
    high: float = 102.0,
    low: float = 98.0,
    close: float = 100.0,
    volume: int = 100_000,
):
    """Inserts `days` identical OHLCV candles from start_date onwards."""
    d = date.fromisoformat(start_date)
    for _ in range(days):
        conn.execute(
            "INSERT OR REPLACE INTO ohlcv (ticker, trade_date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticker, d.isoformat(), open_, high, low, close, volume),
        )
        d += timedelta(days=1)


def _add_macro(
    conn: sqlite3.Connection,
    start_date: str,
    days: int,
    vix: float = 15.0,
    regime: str = "NORMAL",
    market_closed: int = 0,
):
    d = date.fromisoformat(start_date)
    for _ in range(days):
        conn.execute(
            "INSERT OR REPLACE INTO macro_daily "
            "(trade_date, regime, india_vix, fii_net_cr, dii_net_cr, "
            " nifty50_trend, nifty500_trend, advance_decline, market_closed) "
            "VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?)",
            (d.isoformat(), regime, vix, market_closed),
        )
        d += timedelta(days=1)


def _add_snapshot(conn: sqlite3.Connection, ticker: str, as_of_date: str, rsi: float = 55.0, extra: dict = None):
    feats = {"rsi_14": rsi}
    if extra:
        feats.update(extra)
    conn.execute(
        "INSERT OR REPLACE INTO feature_snapshots "
        "(ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES (?, ?, 1, ?, '2025-01-01T00:00:00')",
        (ticker, as_of_date, json.dumps(feats)),
    )


class _NoCloseConn:
    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture()
def _db_container(monkeypatch):
    """
    Builds in-memory ohlcv and macro connections, patches forensics.get_connection
    to return them wrapped in _NoCloseConn so forensics.run() does not close them.
    """
    import types

    _ohlcv = _NoCloseConn(_ohlcv_conn())
    _macro = _NoCloseConn(_macro_conn())

    def fake_get_connection(path: str = None):
        from core.config import settings

        if path == settings.OHLCV_DB_PATH:
            return _ohlcv
        if path == settings.MACRO_DB_PATH:
            return _macro
        from core.database import get_connection as _real

        return _real(path)

    monkeypatch.setattr(forensics, "get_connection", fake_get_connection)

    return types.SimpleNamespace(ohlcv=_ohlcv, macro=_macro)


# Convenience fixtures that delegate to _db_container
@pytest.fixture()
def ohlcv_conn(_db_container):
    return _db_container.ohlcv


@pytest.fixture()
def macro_conn(_db_container):
    return _db_container.macro


@pytest.fixture()
def pconn():

    return _portfolio_conn()


@pytest.fixture()
def clock():
    from core.clock import FakeClock

    return FakeClock(datetime(2025, 1, 10, 16, 0))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCorpActionArtifact:
    def test_classified_on_corp_action_close(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, exit_reason="CORP_ACTION_CLOSE", pnl_pct=-5.0, hold_days=2)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8)
        _add_macro(macro_conn, "2025-01-01", 8)
        r = forensics.run(pconn, pid, clock)
        assert r is not None
        assert r.forensics_type == "CORP_ACTION_ARTIFACT"
        # Check DB was updated
        row = pconn.execute("SELECT forensics_type FROM positions WHERE id=?", (pid,)).fetchone()
        assert row["forensics_type"] == "CORP_ACTION_ARTIFACT"


class TestBroadMarketDrag:
    def test_vix_elevated_majority_of_days(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=-4.0, hold_days=4)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, close=97.0)
        # 6 of 8 days ELEVATED/PANIC
        _add_macro(macro_conn, "2025-01-01", 2, vix=15.0, regime="NORMAL")
        _add_macro(macro_conn, "2025-01-03", 6, vix=25.0, regime="ELEVATED")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "BROAD_MARKET_DRAG"
        diag = json.loads(r.diagnosis_json)
        assert diag["broad_drag_ratio"] >= 0.5

    def test_normal_vix_not_classified_as_broad_drag(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=-3.0, hold_days=5)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, close=97.0)
        _add_macro(macro_conn, "2025-01-01", 8, vix=14.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type != "BROAD_MARKET_DRAG"


class TestRegimeMismatch:
    def test_rising_vix_above_threshold(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=-3.5, hold_days=5)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, close=96.0)
        # VIX starts at 18, ends at 22 (above 20 threshold, rising).
        # 6 days NORMAL, 2 days ELEVATED -> elevated ratio 2/8 (25% < 50%), avoids broad drag.
        _add_macro(macro_conn, "2025-01-01", 6, vix=18.0, regime="NORMAL")
        _add_macro(macro_conn, "2025-01-07", 2, vix=22.0, regime="ELEVATED")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "REGIME_MISMATCH"

    def test_falling_vix_not_regime_mismatch(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=-2.0, hold_days=5)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, close=98.0)
        # VIX starts high, ends lower — not a regime mismatch
        _add_macro(macro_conn, "2025-01-01", 4, vix=22.0, regime="ELEVATED")
        _add_macro(macro_conn, "2025-01-05", 4, vix=17.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type != "REGIME_MISMATCH"


class TestEarningsShock:
    def test_large_intraday_move_flagged(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=-8.0, hold_days=2)
        # One candle with 10% move (open=100, close=90)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 1, open_=100.0, close=90.0)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-02", 7, open_=90.0, close=89.0)
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "EARNINGS_SHOCK"
        diag = json.loads(r.diagnosis_json)
        assert diag["max_single_day_move_pct"] >= 7.0

    def test_small_move_not_flagged(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=-2.0, hold_days=5)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, open_=100.0, close=99.0)
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type != "EARNINGS_SHOCK"


class TestFalseBreakout:
    def test_close_below_entry_no_volume_surge(self, pconn, ohlcv_conn, macro_conn, clock):
        # Entry price = Rs 100 (10000 paise). Close drops to 97 on day 1, low volume.
        pid = _insert_position(
            pconn,
            entry_price_paise=10000,
            pnl_pct=-3.0,
            hold_days=5,
        )
        # Low volume candles (20d avg will be 0 since no pre-entry data → vol_20d_avg=0)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, open_=100.0, close=97.0, volume=50_000)
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "FALSE_BREAKOUT"

    def test_close_above_entry_no_false_breakout(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, entry_price_paise=10000, pnl_pct=-1.0, hold_days=5)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, open_=100.0, close=105.0, volume=50_000)
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type != "FALSE_BREAKOUT"


class TestUnclassified:
    def test_loss_with_no_matching_class(self, pconn, ohlcv_conn, macro_conn, clock):
        # Small loss, normal VIX, no big moves, no early fall below entry in first 3 sessions
        pid = _insert_position(
            pconn,
            entry_price_paise=10000,
            pnl_pct=-1.0,
            hold_days=5,
        )
        # First 3 sessions stay above entry (101.0 >= 100.0) -> no false breakout
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 3, open_=100.0, close=101.0, volume=100_000)
        # Remaining sessions drop to 99.0 -> loss at exit
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-04", 5, open_=100.0, close=99.0, volume=100_000)
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "UNCLASSIFIED"


class TestWinClasses:
    def test_earnings_momentum_win(self, pconn, ohlcv_conn, macro_conn, clock):
        # Big win (pnl 8%, 5 days) with a 6% single-day move
        pid = _insert_position(pconn, pnl_pct=8.0, hold_days=5, exit_reason="AGENT_SELL")
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 1, open_=100.0, close=106.0)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-02", 7, open_=106.0, close=108.0)
        _add_macro(macro_conn, "2025-01-01", 8, vix=14.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "EARNINGS_MOMENTUM"

    def test_mean_reversion_win(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=5.0, hold_days=4, exit_reason="AGENT_SELL")
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, open_=100.0, close=102.0)
        _add_macro(macro_conn, "2025-01-01", 8, vix=14.0, regime="NORMAL")
        # RSI at entry = 32 (oversold)
        _add_snapshot(pconn, "RELIANCE", "2025-01-01", rsi=32.0)
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "MEAN_REVERSION"

    def test_trend_continuation_win(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=6.0, hold_days=7, exit_reason="AGENT_SELL")
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, open_=100.0, close=102.0)
        _add_macro(macro_conn, "2025-01-01", 8, vix=14.0, regime="NORMAL")
        # RSI at entry normal (not oversold)
        _add_snapshot(pconn, "RELIANCE", "2025-01-01", rsi=60.0)
        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "TREND_CONTINUATION"

    def test_win_below_threshold_not_classified_as_win(self, pconn, ohlcv_conn, macro_conn, clock):
        # PnL 3% (below 4%) and hold 5 days — goes through loss path
        pid = _insert_position(pconn, pnl_pct=3.0, hold_days=5, exit_reason="AGENT_SELL")
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, open_=100.0, close=103.0)
        _add_macro(macro_conn, "2025-01-01", 8, vix=14.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        diag = json.loads(r.diagnosis_json)
        assert diag["is_win"] is False


class TestDiagnosisJson:
    def test_always_includes_raw_metrics(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=-2.0, hold_days=3)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8)
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        diag = json.loads(r.diagnosis_json)
        required_keys = {
            "ticker",
            "entry_date",
            "exit_date",
            "hold_days",
            "realized_pnl_pct",
            "entry_price_rupees",
            "exit_reason",
            "vix_at_entry",
            "vix_at_exit",
            "regime_at_exit",
            "max_single_day_move_pct",
            "entry_rsi_14",
            "ohlcv_rows_in_window",
            "is_win",
            "forensics_type",
            "reason",
        }
        assert required_keys.issubset(diag.keys())

    def test_db_columns_updated(self, pconn, ohlcv_conn, macro_conn, clock):
        pid = _insert_position(pconn, pnl_pct=-2.0, hold_days=3)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8)
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")
        forensics.run(pconn, pid, clock)
        row = pconn.execute(
            "SELECT forensics_type, regime_at_exit, diagnosis_json FROM positions WHERE id=?",
            (pid,),
        ).fetchone()
        assert row["forensics_type"] is not None
        assert row["regime_at_exit"] is not None
        assert json.loads(row["diagnosis_json"])  # valid JSON


class TestMissingData:
    def test_no_ohlcv_data_still_classifies(self, pconn, ohlcv_conn, macro_conn, clock):
        """With no OHLCV rows, the engine should not crash; UNCLASSIFIED expected."""
        pid = _insert_position(pconn, pnl_pct=-2.0, hold_days=3)
        # No OHLCV rows inserted
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")
        r = forensics.run(pconn, pid, clock)
        assert r is not None
        assert r.forensics_type in {
            "CORP_ACTION_ARTIFACT",
            "BROAD_MARKET_DRAG",
            "REGIME_MISMATCH",
            "EARNINGS_SHOCK",
            "FALSE_BREAKOUT",
            "UNCLASSIFIED",
        }

    def test_position_not_found_returns_none(self, pconn, ohlcv_conn, macro_conn, clock):
        r = forensics.run(pconn, position_id=99999, clock=clock)
        assert r is None


class TestMultiArchetypeForensics:
    def test_false_breakout_not_applied_to_lynch_garp(self, pconn, ohlcv_conn, macro_conn, clock):
        """
        Lynch is GARP (30-90d horizon). Short-term dip below entry in first 3 days
        must NOT trigger FALSE_BREAKOUT. Since hold_days < 20 (eval horizon) and exit was STOP_HIT,
        it classifies as PREMATURE_TECHNICAL_STOPOUT.
        """
        pid = _insert_position(
            pconn,
            agent_id="lynch",
            entry_price_paise=10000,
            pnl_pct=-3.0,
            hold_days=5,
        )
        # Drop below entry in first 3 days
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 3, open_=100.0, close=97.0, volume=100_000)
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-04", 5, open_=97.0, close=97.0, volume=100_000)
        _add_macro(macro_conn, "2025-01-01", 8, vix=15.0, regime="NORMAL")

        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type != "FALSE_BREAKOUT"
        assert r.forensics_type == "PREMATURE_TECHNICAL_STOPOUT"

    def test_fundamental_derating_for_lynch_beyond_horizon(self, pconn, ohlcv_conn, macro_conn, clock):
        """
        Lynch position held >= 60 days with loss <= -5.0% without macro drag
        is classified as FUNDAMENTAL_DERATING.
        """
        pid = _insert_position(
            pconn,
            agent_id="lynch",
            entry_price_paise=10000,
            pnl_pct=-6.5,
            hold_days=65,
        )
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 65, open_=100.0, close=93.5, volume=100_000)
        _add_macro(macro_conn, "2025-01-01", 65, vix=15.0, regime="NORMAL")

        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "FUNDAMENTAL_DERATING"

    def test_value_trap_for_marks(self, pconn, ohlcv_conn, macro_conn, clock):
        """
        Howard Marks position held >= 60 days with loss <= -5.0%
        and no single-day shock move is classified as VALUE_TRAP.
        """
        pid = _insert_position(
            pconn,
            agent_id="marks",
            entry_price_paise=10000,
            pnl_pct=-8.0,
            hold_days=65,
        )
        # Small daily move (open=93, close=92 -> ~1%), but holding loss is -8%
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 65, open_=93.0, close=92.0, volume=100_000)
        _add_macro(macro_conn, "2025-01-01", 65, vix=16.0, regime="NORMAL")

        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "VALUE_TRAP"

    def test_valuation_rerating_win_for_lynch(self, pconn, ohlcv_conn, macro_conn, clock):
        """
        Lynch multi-week win (PnL >= 10%, hold >= 15d) with steady gains
        and no single-day 5% momentum shock is classified as VALUATION_RERATING.
        """
        pid = _insert_position(
            pconn,
            agent_id="lynch",
            pnl_pct=12.0,
            hold_days=25,
            exit_reason="AGENT_SELL",
        )
        # Small daily move (<5%), holding gain is +12%
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 25, open_=111.0, close=112.0)
        _add_macro(macro_conn, "2025-01-01", 25, vix=14.0, regime="NORMAL")

        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "VALUATION_RERATING"

    def test_contrarian_rebound_win_for_marks(self, pconn, ohlcv_conn, macro_conn, clock):
        """
        Howard Marks win (PnL >= 6%, hold >= 14d, RSI >= 40 at entry) is classified as CONTRARIAN_REBOUND.
        """
        pid = _insert_position(
            pconn,
            agent_id="marks",
            pnl_pct=7.5,
            hold_days=15,
            exit_reason="AGENT_SELL",
        )
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 15, open_=107.0, close=107.5)
        _add_macro(macro_conn, "2025-01-01", 15, vix=14.0, regime="NORMAL")
        # Entry RSI is not oversold (e.g. 50), stored in portfolio_conn
        _add_snapshot(pconn, "RELIANCE", "2025-01-01", rsi=50.0)

        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "CONTRARIAN_REBOUND"

    def test_institutional_sponsorship_breach_for_jhunjhunwala(self, pconn, ohlcv_conn, macro_conn, clock):
        """
        Jhunjhunwala (GROWTH_COMPOUNDER) suffering institutional outflow (fii_dii_qoq_delta_pct < 0)
        is classified as INSTITUTIONAL_SPONSORSHIP_BREACH on loss exit.
        """
        pid = _insert_position(
            pconn,
            agent_id="jhunjhunwala",
            entry_price_paise=10000,
            pnl_pct=-4.0,
            hold_days=15,
        )
        _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 15, open_=98.0, close=96.0, volume=100_000)
        _add_macro(macro_conn, "2025-01-01", 15, vix=15.0, regime="NORMAL")
        _add_snapshot(pconn, "RELIANCE", "2025-01-08", rsi=50.0, extra={"fii_dii_qoq_delta_pct": -2.4})

        r = forensics.run(pconn, pid, clock)
        assert r.forensics_type == "INSTITUTIONAL_SPONSORSHIP_BREACH"
        diag = json.loads(r.diagnosis_json)
        assert diag["fii_dii_qoq_delta_pct"] == -2.4
