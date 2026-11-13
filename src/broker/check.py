"""
`python -m broker.check`: verifies broker invariants against the real portfolio.db and prints
OK or the violations found.
See Plan_v3 §4.2, §4.3.
"""

import sqlite3
import sys

from broker.engine import Broker
from core.clock import SystemClock
from core.config import settings
from core.database import get_connection


def check_invariants(conn: sqlite3.Connection) -> list[str]:
    violations: list[str] = []
    broker = Broker(conn, SystemClock())

    for agent in conn.execute("SELECT id, cash_paise, starting_cash_paise FROM agents").fetchall():
        agent_id = agent["id"]

        if agent["cash_paise"] < 0:
            violations.append(f"{agent_id}: negative cash_paise={agent['cash_paise']}")

        independent_reserved = conn.execute(
            "SELECT COALESCE(SUM(reserved_amount_paise), 0) AS total FROM pending_orders "
            "WHERE agent_id = ? AND side = 'BUY' AND status = 'pending'",
            (agent_id,),
        ).fetchone()["total"]
        broker_reserved = broker.reserved_cash_paise(agent_id)
        if independent_reserved != broker_reserved:
            violations.append(
                f"{agent_id}: reserved_cash_paise mismatch broker={broker_reserved} query={independent_reserved}"
            )

        available = agent["cash_paise"] - independent_reserved
        if available < 0:
            violations.append(f"{agent_id}: available cash negative ({available})")

        for row in conn.execute(
            "SELECT ticker, COUNT(*) AS n FROM positions WHERE agent_id = ? AND status = 'OPEN' "
            "GROUP BY ticker HAVING n > 1",
            (agent_id,),
        ).fetchall():
            violations.append(f"{agent_id}: {row['ticker']} has {row['n']} OPEN positions")

        for row in conn.execute(
            "SELECT id, ticker, shares, stop_paise, target_paise FROM positions "
            "WHERE agent_id = ? AND status = 'OPEN' AND (shares <= 0 OR stop_paise >= target_paise)",
            (agent_id,),
        ).fetchall():
            violations.append(
                f"{agent_id}: position {row['id']} ({row['ticker']}) invalid "
                f"shares={row['shares']} stop={row['stop_paise']} target={row['target_paise']}"
            )

        for order in conn.execute(
            "SELECT id, ticker FROM pending_orders WHERE agent_id = ? AND status = 'filled'", (agent_id,)
        ).fetchall():
            if conn.execute("SELECT 1 FROM fills WHERE order_id = ? LIMIT 1", (order["id"],)).fetchone() is None:
                violations.append(f"{agent_id}: filled order {order['id']} ({order['ticker']}) has no fill row")
            if (
                conn.execute(
                    "SELECT 1 FROM positions WHERE agent_id = ? AND ticker = ? LIMIT 1", (agent_id, order["ticker"])
                ).fetchone()
                is None
            ):
                violations.append(f"{agent_id}: filled order {order['id']} ({order['ticker']}) has no position row")

        replayed_cash = agent["starting_cash_paise"]
        for fill in conn.execute(
            "SELECT side, shares, price_paise, charges_paise FROM fills WHERE agent_id = ? ORDER BY id", (agent_id,)
        ).fetchall():
            if fill["side"] == "BUY":
                replayed_cash -= fill["shares"] * fill["price_paise"] + fill["charges_paise"]
            else:
                replayed_cash += fill["shares"] * fill["price_paise"] - fill["charges_paise"]
        if replayed_cash != agent["cash_paise"]:
            violations.append(f"{agent_id}: cash replay mismatch replayed={replayed_cash} actual={agent['cash_paise']}")

    return violations


def main() -> int:
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        violations = check_invariants(conn)
    finally:
        conn.close()
    if not violations:
        print("OK")
        return 0
    print(f"{len(violations)} violation(s):")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
