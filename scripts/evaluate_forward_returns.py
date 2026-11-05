"""
Comprehensive Forward Returns and Portfolio NAV Trajectory Evaluator.
Evaluates:
1. Decision Forward Returns (T+1, T+5, T+10, T+18) for all decision candidates vs Nifty 500
2. Multi-day Portfolio NAV Trajectory & Position Lifecycle day-by-day across the full month
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from broker.engine import Broker
from broker.settlement import run_settlement
from core.clock import Clock
from core.database import get_connection
from core.money import paise_to_rupees, rupees_to_paise
from evaluation.forward_returns import compute_forward_returns, get_forward_trading_dates, get_universe_mean_return
from settings import settings

IST = ZoneInfo("Asia/Kolkata")


class SimulatedClock(Clock):
    def __init__(self, current_dt: datetime):
        self._dt = current_dt

    def set_time(self, new_dt: datetime) -> None:
        self._dt = new_dt

    def now(self) -> datetime:
        return self._dt

    def today(self) -> date:
        return self._dt.date()

    def now_iso(self) -> str:
        return self._dt.isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward Returns and Multi-day NAV Trajectory Evaluator.")
    parser.add_argument("--db", default="storage/ledger/simulation.db", help="Path to simulation database")
    parser.add_argument("--decision-date", default="2026-09-25", help="Run date of decisions (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="End date for forward horizon (YYYY-MM-DD)")
    args = parser.parse_args()

    sim_db_path = Path(args.db).resolve()
    ohlcv_db_path = Path(settings.OHLCV_DB_PATH).resolve()
    decision_date = args.decision_date
    end_date = args.end_date

    print("=" * 90)
    print("STOCKMINDS FORWARD RETURNS & TRAJECTORY EVALUATION")
    print(f"Decision Date:   {decision_date}")
    if end_date:
        print(f"End Date:        {end_date}")
    print(f"Simulation DB:   {sim_db_path}")
    print(f"OHLCV DB:        {ohlcv_db_path}")
    print("=" * 90)

    sim_conn = get_connection(sim_db_path)
    ohlcv_conn = get_connection(ohlcv_db_path)

    # 1. Forward Trading Days
    forward_dates = get_forward_trading_dates(ohlcv_conn, decision_date)
    if end_date:
        forward_dates = [d for d in forward_dates if d <= end_date]

    print(f"\n[PART 1] Detected {len(forward_dates)} Forward Trading Dates:")
    print("  " + ", ".join(forward_dates))

    # Determine Horizons available
    horizons = [1, 5, 10]
    if len(forward_dates) >= 20:
        horizons.append(20)
    if len(forward_dates) not in horizons and len(forward_dates) > 0:
        horizons.append(len(forward_dates))
    horizons = sorted(list(set(horizons)))

    # Compute Forward Returns for all decisions
    clock = SimulatedClock(datetime(2026, 10, 26, 20, 0, tzinfo=IST))
    ret_res = compute_forward_returns(sim_conn, ohlcv_conn, clock=clock, horizons=horizons)
    print(f"\n[PART 2] Decision Forward Returns Computed: {ret_res}")

    # Query & Display Forward Returns Table
    query = """
    SELECT d.id, d.agent_id, d.ticker, d.action, d.shares,
           fr1.ret_pct AS ret_t1, fr1.nifty_ret_pct AS nifty_t1,
           fr5.ret_pct AS ret_t5, fr5.nifty_ret_pct AS nifty_t5,
           fr10.ret_pct AS ret_t10, fr10.nifty_ret_pct AS nifty_t10,
           frL.ret_pct AS ret_tL, frL.nifty_ret_pct AS nifty_tL,
           frL.horizon_days AS last_horizon
    FROM decisions d
    LEFT JOIN forward_returns fr1 ON fr1.decision_id = d.id AND fr1.horizon_days = 1
    LEFT JOIN forward_returns fr5 ON fr5.decision_id = d.id AND fr5.horizon_days = 5
    LEFT JOIN forward_returns fr10 ON fr10.decision_id = d.id AND fr10.horizon_days = 10
    LEFT JOIN forward_returns frL ON frL.decision_id = d.id AND frL.horizon_days = ?
    WHERE d.run_date = ?
    ORDER BY d.action DESC, d.agent_id ASC, d.ticker ASC
    """
    last_h = horizons[-1]
    rows = sim_conn.execute(query, (last_h, decision_date)).fetchall()

    print("\n" + "=" * 90)
    print(f"DECISION FORWARD RETURNS TABLE (Base Date: {decision_date})")
    print(f"Horizons: T+1 ({forward_dates[0]}), T+5 ({forward_dates[4]}), T+10 ({forward_dates[9]}), T+{last_h} ({forward_dates[last_h-1]})")
    print("=" * 90)
    print(f"{'Agent ID':<18} {'Action':<5} {'Ticker':<12} {'T+1 Ret %':<11} {'T+5 Ret %':<11} {'T+10 Ret %':<12} {f'T+{last_h} Ret %':<13} {'T+18 Alpha'}")
    print("-" * 90)

    buy_returns = {1: [], 5: [], 10: [], last_h: []}
    hold_returns = {1: [], 5: [], 10: [], last_h: []}

    for r in rows:
        t1_str = f"{r['ret_t1']:>+7.2f}%" if r['ret_t1'] is not None else "    N/A"
        t5_str = f"{r['ret_t5']:>+7.2f}%" if r['ret_t5'] is not None else "    N/A"
        t10_str = f"{r['ret_t10']:>+7.2f}%" if r['ret_t10'] is not None else "    N/A"
        tL_str = f"{r['ret_tL']:>+7.2f}%" if r['ret_tL'] is not None else "    N/A"
        
        alpha_str = "    N/A"
        if r['ret_tL'] is not None and r['nifty_tL'] is not None:
            alpha = r['ret_tL'] - r['nifty_tL']
            alpha_str = f"{alpha:>+8.2f}%"

        if r['action'] == 'BUY':
            if r['ret_t1'] is not None: buy_returns[1].append(r['ret_t1'])
            if r['ret_t5'] is not None: buy_returns[5].append(r['ret_t5'])
            if r['ret_t10'] is not None: buy_returns[10].append(r['ret_t10'])
            if r['ret_tL'] is not None: buy_returns[last_h].append(r['ret_tL'])
        else:
            if r['ret_t1'] is not None: hold_returns[1].append(r['ret_t1'])
            if r['ret_t5'] is not None: hold_returns[5].append(r['ret_t5'])
            if r['ret_t10'] is not None: hold_returns[10].append(r['ret_t10'])
            if r['ret_tL'] is not None: hold_returns[last_h].append(r['ret_tL'])

        print(f"{r['agent_id']:<18} {r['action']:<5} {r['ticker']:<12} {t1_str:<11} {t5_str:<11} {t10_str:<12} {tL_str:<13} {alpha_str}")

    print("-" * 90)
    # Benchmark Row
    if rows and rows[0]['nifty_t1'] is not None:
        b_t1 = f"{rows[0]['nifty_t1']:>+7.2f}%"
        b_t5 = f"{rows[0]['nifty_t5']:>+7.2f}%"
        b_t10 = f"{rows[0]['nifty_t10']:>+7.2f}%"
        b_tL = f"{rows[0]['nifty_tL']:>+7.2f}%"
        print(f"{'[BENCHMARK NIFTY500]':<36} {b_t1:<11} {b_t5:<11} {b_t10:<12} {b_tL:<13}    0.00%")

    if buy_returns[last_h]:
        avg_buy = sum(buy_returns[last_h]) / len(buy_returns[last_h])
        avg_hold = sum(hold_returns[last_h]) / len(hold_returns[last_h]) if hold_returns[last_h] else 0.0
        print(f"\n  Summary over T+{last_h} Trading Days:")
        print(f"  -> Average BUY decisions return:  {avg_buy:>+7.2f}%")
        print(f"  -> Average HOLD decisions return: {avg_hold:>+7.2f}%")
        print(f"  -> Selection Alpha (BUY vs HOLD): {avg_buy - avg_hold:>+7.2f}%")

    # 3. Multi-day Portfolio NAV Trajectory & Position Lifecycle
    print("\n" + "=" * 90)
    print("MULTI-DAY PORTFOLIO TRAJECTORY (Sep 28 -> Oct 23, 2026)")
    print("=" * 90)

    # Initial Nifty close proxy
    nifty_base = 23550.50
    daily_trajectory = []

    # Get active agents
    agents = sim_conn.execute("SELECT id FROM agents").fetchall()
    agent_ids = [a["id"] for a in agents]

    for day_idx, current_date in enumerate(forward_dates):
        d_obj = date.fromisoformat(current_date)
        clock.set_time(datetime(d_obj.year, d_obj.month, d_obj.day, 15, 30, tzinfo=IST))
        broker = Broker(sim_conn, clock)

        # 1. Fetch candles for open positions on current_date
        open_pos = sim_conn.execute("SELECT * FROM positions WHERE status = 'OPEN'").fetchall()
        pos_tickers = list({p["ticker"] for p in open_pos})

        candles = {}
        if pos_tickers:
            placeholders = ",".join("?" * len(pos_tickers))
            c_rows = ohlcv_conn.execute(
                f"SELECT ticker, open, high, low, close FROM ohlcv WHERE trade_date = ? AND ticker IN ({placeholders})",
                (current_date, *pos_tickers),
            ).fetchall()
            candles = {r["ticker"]: r for r in c_rows}

        # 2. Check stop hits and update prices
        for p in open_pos:
            ticker = p["ticker"]
            if ticker in candles:
                c = candles[ticker]
                low_p = rupees_to_paise(c["low"])
                close_p = rupees_to_paise(c["close"])

                # Check Stop Loss
                if low_p <= p["stop_paise"]:
                    exit_price_p = min(p["stop_paise"], rupees_to_paise(c["open"]))
                    broker.close_position(p["id"], exit_price_p, "STOP_HIT")
                    # print(f"     [STOP HIT] {current_date}: Position #{p['id']} [{p['agent_id']}] {ticker} stopped at Rs {paise_to_rupees(exit_price_p):.2f}")
                else:
                    # Update last price to day's close
                    sim_conn.execute(
                        "UPDATE positions SET last_price_paise = ? WHERE id = ?",
                        (close_p, p["id"]),
                    )

        # 3. Settlement for current_date
        clock.set_time(datetime(d_obj.year, d_obj.month, d_obj.day, 15, 35, tzinfo=IST))
        # Nifty return proxy
        nifty_ret = get_universe_mean_return(ohlcv_conn, decision_date, current_date)
        nifty_close_cur = nifty_base * (1.0 + nifty_ret / 100.0)

        run_settlement(sim_conn, clock, quote_provider=None, run_date_str=current_date, nifty500_close=nifty_close_cur)

        # Query NAV for this day
        nav_map = {}
        for a_id in agent_ids:
            row = sim_conn.execute(
                "SELECT total_paise FROM daily_nav WHERE agent_id = ? AND nav_date = ?",
                (a_id, current_date),
            ).fetchone()
            if row:
                nav_rs = float(paise_to_rupees(row["total_paise"]))
                ret_pct = ((nav_rs - 1000000.0) / 1000000.0) * 100.0
                nav_map[a_id] = (nav_rs, ret_pct)
        daily_trajectory.append((current_date, nifty_ret, nav_map))

    # Print Daily Trajectory Summary Table
    print(f"{'Date':<12} {'Nifty %':<10} {'Simons %':<11} {'Lynch %':<11} {'Marks %':<11} {'Jhunjhunwala %':<15} {'StockMinds-Core %':<18} {'Rules Baseline %'}")
    print("-" * 105)

    sample_dates = daily_trajectory[::2]  # every other day
    if daily_trajectory[-1] not in sample_dates:
        sample_dates.append(daily_trajectory[-1])

    for d_str, n_ret, n_map in sample_dates:
        sim_ret = n_map.get("simons", (0, 0.0))[1]
        lyn_ret = n_map.get("lynch", (0, 0.0))[1]
        mar_ret = n_map.get("marks", (0, 0.0))[1]
        jhun_ret = n_map.get("jhunjhunwala", (0, 0.0))[1]
        core_ret = n_map.get("varsity", (0, 0.0))[1]
        base_ret = n_map.get("baseline-simons-rules", (0, 0.0))[1]

        print(f"{d_str:<12} {n_ret:>+7.2f}%   {sim_ret:>+8.2f}%   {lyn_ret:>+8.2f}%   {mar_ret:>+8.2f}%   {jhun_ret:>+10.2f}%      {core_ret:>+12.2f}%       {base_ret:>+10.2f}%")

    # 4. Final Cumulative Summary
    print("\n" + "=" * 90)
    print("CUMULATIVE PERFORMANCE METRICS (Full Month to Oct 23, 2026)")
    print("=" * 90)
    print(f"{'Agent ID':<22} {'Initial NAV':<14} {'Final NAV (Rs)':<16} {'Total Ret %':<12} {'Open Pos':<10} {'Closed Pos':<10}")
    print("-" * 90)

    for a_id in sorted(agent_ids, key=lambda x: daily_trajectory[-1][2].get(x, (0, 0))[1], reverse=True):
        final_nav, final_ret = daily_trajectory[-1][2].get(a_id, (1000000.0, 0.0))
        open_cnt = sim_conn.execute("SELECT count(*) FROM positions WHERE agent_id = ? AND status = 'OPEN'", (a_id,)).fetchone()[0]
        closed_cnt = sim_conn.execute("SELECT count(*) FROM positions WHERE agent_id = ? AND status = 'CLOSED'", (a_id,)).fetchone()[0]
        print(f"{a_id:<22} Rs 10,00,000   Rs {final_nav:>12,.2f}   {final_ret:>+8.2f}%     {open_cnt:<10} {closed_cnt:<10}")

    final_nifty = daily_trajectory[-1][1]
    print(f"{'[NIFTY 500 BENCHMARK]':<38} {final_nifty:>+8.2f}%")
    print("=" * 90)

    sim_conn.close()
    ohlcv_conn.close()


if __name__ == "__main__":
    main()
