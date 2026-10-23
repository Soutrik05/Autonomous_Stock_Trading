"""
Validation, orders, reservation, fills, averaging and ADJUST handling for the paper broker.
No monitor, expiry or settlement yet -- this module only places orders from saved decisions
and fills them when told to (fill_buy/fill_sell/close_position), for the monitor job to call
once it exists.
See Plan_v3 §4.2, §4.3.
"""
import json
import logging
import sqlite3
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from broker.transaction_charges import apply_slippage, compute_transaction_charges_paise
from core.calendar import is_trading_day, next_trading_day
from core.clock import Clock
from settings import settings

logger = logging.getLogger(__name__)


def _col(row, key):
    return row[key] if row is not None else None


class Broker:
    def __init__(self, conn: sqlite3.Connection, clock: Clock):
        self.conn = conn
        self.clock = clock

    # --- cash / reservation (derived, never stored) --------------------------------------------

    def reserved_cash_paise(self, agent_id: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(reserved_amount_paise), 0) AS total FROM pending_orders "
            "WHERE agent_id = ? AND side = 'BUY' AND status = 'pending'",
            (agent_id,),
        ).fetchone()
        return row["total"]

    def available_cash_paise(self, agent_id: str) -> int:
        row = self.conn.execute("SELECT cash_paise FROM agents WHERE id = ?", (agent_id,)).fetchone()
        cash = row["cash_paise"] if row else 0
        return cash - self.reserved_cash_paise(agent_id)

    def worst_case_buy_outlay_paise(self, shares: int, entry_high_paise: int) -> int:
        """Worst fill price = entry_high x (1 + BUY_OVERSHOOT_PCT%), then slippage; outlay =
        shares x that price + BUY charges at that price."""
        overshoot = Decimal(1) + Decimal(str(settings.BUY_OVERSHOOT_PCT)) / Decimal(100)
        worst_price = int((Decimal(entry_high_paise) * overshoot).to_integral_value(rounding=ROUND_HALF_UP))
        worst_price = apply_slippage(worst_price, "BUY")
        charges = compute_transaction_charges_paise(worst_price, shares, "BUY")
        return shares * worst_price + charges

    # --- order validity date ---------------------------------------------------------------------

    def order_valid_date(self, run_date: date) -> date:
        """NEXT_TRADING_DAY (default): next_trading_day(run_date). SAME_DAY_IF_BEFORE_OPEN: if
        run_date is a trading day and the Clock's current time is before MARKET_OPEN_TIME
        (09:15 IST), run_date itself; otherwise the next trading day."""
        if settings.ORDER_VALIDITY_MODE == "SAME_DAY_IF_BEFORE_OPEN":
            open_h, open_m = (int(p) for p in settings.MARKET_OPEN_TIME.split(":"))
            now = self.clock.now()
            before_open = (now.hour, now.minute) < (open_h, open_m)
            if before_open and is_trading_day(self.conn, run_date):
                return run_date
        return next_trading_day(self.conn, run_date)

    # --- activity log ------------------------------------------------------------------------------

    def _log_activity(self, agent_id: Optional[str], event_type: str, ticker: Optional[str],
                       description: str, metadata: dict) -> None:
        self.conn.execute(
            "INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, event_type, ticker, description, json.dumps(metadata), self.clock.now_iso()),
        )

    def _log_cap_breach(self, agent_id: str, ticker: str, cap: str, measured: float, limit: float, decision_id: int) -> None:
        self._log_activity(
            agent_id, "CAP_BREACH", ticker, f"{cap} measured={measured:.2f} limit={limit}",
            {"decision_id": decision_id, "cap": cap, "measured": round(measured, 4), "limit": limit},
        )

    # --- lookups -------------------------------------------------------------------------------------

    def _get_open_position(self, agent_id: str, ticker: str):
        return self.conn.execute(
            "SELECT * FROM positions WHERE agent_id = ? AND ticker = ? AND status = 'OPEN'",
            (agent_id, ticker),
        ).fetchone()

    def _sector_for_ticker(self, ticker: str) -> str:
        row = self.conn.execute("SELECT sector FROM symbols WHERE ticker = ?", (ticker,)).fetchone()
        return row["sector"] if row else "UNKNOWN"

    def _account_value_paise(self, agent_id: str) -> int:
        cash = _col(self.conn.execute("SELECT cash_paise FROM agents WHERE id = ?", (agent_id,)).fetchone(), "cash_paise") or 0
        invested = self.conn.execute(
            "SELECT COALESCE(SUM(shares * last_price_paise), 0) AS total FROM positions "
            "WHERE agent_id = ? AND status = 'OPEN'",
            (agent_id,),
        ).fetchone()["total"]
        return cash + invested

    def _sector_value_paise(self, agent_id: str, sector: str) -> int:
        return self.conn.execute(
            "SELECT COALESCE(SUM(shares * last_price_paise), 0) AS total FROM positions "
            "WHERE agent_id = ? AND status = 'OPEN' AND sector = ?",
            (agent_id, sector),
        ).fetchone()["total"]

    def _open_position_count(self, agent_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM positions WHERE agent_id = ? AND status = 'OPEN'", (agent_id,)
        ).fetchone()["n"]

    def _decision_already_processed(self, decision) -> bool:
        if self.conn.execute(
            "SELECT 1 FROM pending_orders WHERE decision_id = ? LIMIT 1", (decision["id"],)
        ).fetchone():
            return True
        # ADJUST creates no order row; its idempotency marker is the activity_log entry.
        rows = self.conn.execute(
            "SELECT metadata_json FROM activity_log WHERE event_type = 'ADJUSTED' "
            "AND agent_id = ? AND ticker = ?",
            (decision["agent_id"], decision["ticker"]),
        ).fetchall()
        for row in rows:
            if json.loads(row["metadata_json"] or "{}").get("decision_id") == decision["id"]:
                return True
        return False

    def _cancel_existing_pending(self, agent_id: str, ticker: str) -> None:
        now = self.clock.now_iso()
        for row in self.conn.execute(
            "SELECT id FROM pending_orders WHERE agent_id = ? AND ticker = ? AND status = 'pending'",
            (agent_id, ticker),
        ).fetchall():
            self.conn.execute(
                "UPDATE pending_orders SET status = 'cancelled', updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )

    # --- placing orders from saved decisions ----------------------------------------------------------

    def place_orders_for_run(self, agent_id: str, run_date: str) -> dict:
        """Idempotent: a decision that already has an order row (or, for ADJUST, an ADJUSTED
        activity_log entry) is skipped. Processes ADJUST, then SELL, then BUY (by watchlist
        intensity_score descending, not-in-watchlist last, ties by ticker) so cash rejections
        are deterministic."""
        run_date_obj = date.fromisoformat(run_date)
        valid_for_date = self.order_valid_date(run_date_obj).isoformat()

        decisions = self.conn.execute(
            """
            SELECT d.*, w.intensity_score AS watchlist_intensity
            FROM decisions d
            LEFT JOIN agent_watchlist w ON w.agent_id = d.agent_id AND w.ticker = d.ticker
            WHERE d.agent_id = ? AND d.run_date = ?
            ORDER BY
                CASE d.action WHEN 'ADJUST' THEN 0 WHEN 'SELL' THEN 1 WHEN 'BUY' THEN 2 ELSE 3 END,
                w.intensity_score DESC,
                d.ticker ASC
            """,
            (agent_id, run_date),
        ).fetchall()

        summary = {"orders_created": 0, "rejected": 0, "adjusted": 0, "sells": 0, "skipped_existing": 0}
        for decision in decisions:
            if decision["action"] == "HOLD":
                continue
            if self._decision_already_processed(decision):
                summary["skipped_existing"] += 1
                continue
            if decision["action"] == "ADJUST":
                self._process_adjust(decision)
                summary["adjusted"] += 1
            elif decision["action"] == "SELL":
                if self._process_sell(decision, valid_for_date):
                    summary["sells"] += 1
                else:
                    summary["rejected"] += 1
            elif decision["action"] == "BUY":
                if self._process_buy(decision, valid_for_date):
                    summary["orders_created"] += 1
                else:
                    summary["rejected"] += 1
        return summary

    def _reject_order(self, decision, side: str, reason: str, valid_for_date: str) -> None:
        now = self.clock.now_iso()
        self.conn.execute(
            """
            INSERT INTO pending_orders
                (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, stop_paise,
                 target_paise, reserved_amount_paise, decision_id, status, rejection_reason,
                 valid_for_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'rejected', ?, ?, ?, ?)
            """,
            (decision["agent_id"], decision["ticker"], side, decision["shares"] or 0,
             decision["entry_low_paise"], decision["entry_high_paise"], decision["stop_paise"],
             decision["target_paise"], decision["id"], reason, valid_for_date, now, now),
        )
        self._log_activity(
            decision["agent_id"], "VALIDATION_FAILED", decision["ticker"],
            f"{side} rejected: {reason}", {"decision_id": decision["id"], "reason": reason},
        )

    def _process_buy(self, decision, valid_for_date: str) -> bool:
        agent_id, ticker = decision["agent_id"], decision["ticker"]
        shares = decision["shares"]
        entry_low, entry_high = decision["entry_low_paise"], decision["entry_high_paise"]
        stop, target = decision["stop_paise"], decision["target_paise"]

        price_logic_ok = (
            shares is not None and shares >= 1
            and None not in (stop, entry_low, entry_high, target)
            and 0 < stop < entry_low <= entry_high < target
        )
        if not price_logic_ok:
            self._reject_order(decision, "BUY", "INVALID_PRICES", valid_for_date)
            return False

        outlay = self.worst_case_buy_outlay_paise(shares, entry_high)
        if self.available_cash_paise(agent_id) < outlay:
            self._reject_order(decision, "BUY", "INSUFFICIENT_CASH", valid_for_date)
            return False

        # A pending order (any side) left over for this ticker would violate the one-pending-
        # per-ticker index; replace it, same as the explicit SELL "replaces it" rule.
        self._cancel_existing_pending(agent_id, ticker)

        now = self.clock.now_iso()
        self.conn.execute(
            """
            INSERT INTO pending_orders
                (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, stop_paise,
                 target_paise, reserved_amount_paise, decision_id, status, valid_for_date,
                 created_at, updated_at)
            VALUES (?, ?, 'BUY', ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (agent_id, ticker, shares, entry_low, entry_high, stop, target, outlay,
             decision["id"], valid_for_date, now, now),
        )
        order_id = self.conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        self._log_activity(
            agent_id, "ORDER_SUBMITTED", ticker,
            f"BUY {shares} {ticker} reserved={outlay}",
            {"decision_id": decision["id"], "order_id": order_id, "reserved_amount_paise": outlay},
        )

        self._check_soft_caps_after_buy(decision, shares, entry_high, stop)
        return True

    def _check_soft_caps_after_buy(self, decision, shares: int, entry_high_paise: int, stop_paise: int) -> None:
        """Soft rules never block the order; each breach is just logged with the measured value."""
        agent_id, ticker = decision["agent_id"], decision["ticker"]
        account_value = self._account_value_paise(agent_id)
        if account_value <= 0:
            return

        risk_pct = shares * (entry_high_paise - stop_paise) / account_value * 100
        if risk_pct > settings.MAX_RISK_PCT_PER_TRADE:
            self._log_cap_breach(agent_id, ticker, "RISK_PCT", risk_pct, settings.MAX_RISK_PCT_PER_TRADE, decision["id"])

        position_value = shares * entry_high_paise
        position_pct = position_value / account_value * 100
        if position_pct > settings.MAX_POSITION_PCT_OF_ACCOUNT:
            self._log_cap_breach(agent_id, ticker, "POSITION_PCT", position_pct, settings.MAX_POSITION_PCT_OF_ACCOUNT, decision["id"])

        sector = self._sector_for_ticker(ticker)
        sector_value_after = self._sector_value_paise(agent_id, sector) + position_value
        sector_pct = sector_value_after / account_value * 100
        if sector_pct > settings.MAX_SECTOR_PCT_OF_ACCOUNT:
            self._log_cap_breach(agent_id, ticker, "SECTOR_PCT", sector_pct, settings.MAX_SECTOR_PCT_OF_ACCOUNT, decision["id"])

        already_held = self._get_open_position(agent_id, ticker) is not None
        position_count_after = self._open_position_count(agent_id) + (0 if already_held else 1)
        if position_count_after > settings.MAX_OPEN_POSITIONS_PER_AGENT:
            self._log_cap_breach(agent_id, ticker, "MAX_POSITIONS", position_count_after, settings.MAX_OPEN_POSITIONS_PER_AGENT, decision["id"])

    def _process_sell(self, decision, valid_for_date: str) -> bool:
        agent_id, ticker = decision["agent_id"], decision["ticker"]
        position = self._get_open_position(agent_id, ticker)
        if position is None:
            self._reject_order(decision, "SELL", "NO_OPEN_POSITION", valid_for_date)
            return False

        self._cancel_existing_pending(agent_id, ticker)  # "a SELL decision ... replaces it"

        now = self.clock.now_iso()
        self.conn.execute(
            """
            INSERT INTO pending_orders
                (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, stop_paise,
                 target_paise, reserved_amount_paise, decision_id, status, valid_for_date,
                 created_at, updated_at)
            VALUES (?, ?, 'SELL', ?, NULL, NULL, ?, ?, 0, ?, 'pending', ?, ?, ?)
            """,
            (agent_id, ticker, position["shares"], position["stop_paise"], position["target_paise"],
             decision["id"], valid_for_date, now, now),
        )
        order_id = self.conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        self._log_activity(
            agent_id, "ORDER_SUBMITTED", ticker, f"SELL {position['shares']} {ticker}",
            {"decision_id": decision["id"], "order_id": order_id},
        )
        return True

    def _process_adjust(self, decision) -> bool:
        agent_id, ticker = decision["agent_id"], decision["ticker"]
        position = self._get_open_position(agent_id, ticker)
        if position is None:
            self._log_activity(
                agent_id, "VALIDATION_FAILED", ticker, "ADJUST rejected: no open position",
                {"decision_id": decision["id"], "reason": "NO_OPEN_POSITION"},
            )
            return False

        new_stop = decision["stop_paise"] if decision["stop_paise"] is not None else position["stop_paise"]
        new_target = decision["target_paise"] if decision["target_paise"] is not None else position["target_paise"]

        if settings.STOP_MAY_ONLY_RISE and new_stop < position["stop_paise"]:
            self._log_activity(
                agent_id, "VALIDATION_FAILED", ticker, "ADJUST rejected: stop may only rise",
                {"decision_id": decision["id"], "reason": "STOP_MAY_NOT_FALL"},
            )
            return False

        last_price = position["last_price_paise"]
        if not (new_stop < last_price < new_target):
            self._log_activity(
                agent_id, "VALIDATION_FAILED", ticker,
                "ADJUST rejected: stop/target must bracket last price",
                {"decision_id": decision["id"], "reason": "INVALID_ADJUST_PRICES"},
            )
            return False

        self.conn.execute(
            "UPDATE positions SET stop_paise = ?, target_paise = ? WHERE id = ?",
            (new_stop, new_target, position["id"]),
        )
        self._log_activity(
            agent_id, "ADJUSTED", ticker, f"stop={new_stop} target={new_target}",
            {"decision_id": decision["id"], "position_id": position["id"],
             "new_stop_paise": new_stop, "new_target_paise": new_target},
        )
        return True

    # --- fills (atomic) -----------------------------------------------------------------------------------

    def fill_buy(self, order_id: int, market_price_paise: int) -> bool:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            now = self.clock.now_iso()
            cur = self.conn.execute(
                "UPDATE pending_orders SET status = 'filled', updated_at = ? WHERE id = ? AND status = 'pending'",
                (now, order_id),
            )
            if cur.rowcount == 0:
                self.conn.execute("ROLLBACK")
                return False

            order = self.conn.execute("SELECT * FROM pending_orders WHERE id = ?", (order_id,)).fetchone()
            fill_price = apply_slippage(market_price_paise, "BUY")
            charges = compute_transaction_charges_paise(fill_price, order["shares"], "BUY")
            cost = order["shares"] * fill_price + charges
            if cost > order["reserved_amount_paise"]:
                raise AssertionError(
                    f"BUY fill cost {cost} exceeds reserved_amount_paise "
                    f"{order['reserved_amount_paise']} for order {order_id}"
                )

            existing = self._get_open_position(order["agent_id"], order["ticker"])
            if existing is None:
                sector = self._sector_for_ticker(order["ticker"])
                decision = self.conn.execute(
                    "SELECT reasoning FROM decisions WHERE id = ?", (order["decision_id"],)
                ).fetchone()
                self.conn.execute(
                    """
                    INSERT INTO positions
                        (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise,
                         target_paise, last_price_paise, status, entry_date, entry_decision_id,
                         entry_reasoning)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)
                    """,
                    (order["agent_id"], order["ticker"], sector, order["shares"], fill_price,
                     order["stop_paise"], order["target_paise"], fill_price,
                     self.clock.today().isoformat(), order["decision_id"],
                     decision["reasoning"] if decision else None),
                )
                position_id = self.conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            else:
                position_id = existing["id"]
                total_shares = existing["shares"] + order["shares"]
                new_avg = (
                    Decimal(existing["shares"]) * Decimal(existing["avg_entry_price_paise"])
                    + Decimal(order["shares"]) * Decimal(fill_price)
                ) / Decimal(total_shares)
                new_avg_int = int(new_avg.to_integral_value(rounding=ROUND_HALF_UP))
                self.conn.execute(
                    "UPDATE positions SET shares = ?, avg_entry_price_paise = ?, stop_paise = ?, "
                    "target_paise = ?, last_price_paise = ? WHERE id = ?",
                    (total_shares, new_avg_int, order["stop_paise"], order["target_paise"], fill_price, position_id),
                )

            self.conn.execute(
                "INSERT INTO fills (order_id, position_id, agent_id, ticker, side, shares, "
                "price_paise, charges_paise, executed_at) VALUES (?, ?, ?, ?, 'BUY', ?, ?, ?, ?)",
                (order_id, position_id, order["agent_id"], order["ticker"], order["shares"], fill_price, charges, now),
            )
            self.conn.execute(
                "UPDATE agents SET cash_paise = cash_paise - ?, updated_at = ? WHERE id = ?",
                (cost, now, order["agent_id"]),
            )
            self._log_activity(
                order["agent_id"], "BUY_FILLED", order["ticker"],
                f"BUY {order['shares']} {order['ticker']} @ {fill_price} charges={charges}",
                {"order_id": order_id, "position_id": position_id, "fill_price_paise": fill_price, "charges_paise": charges},
            )
            self.conn.execute("COMMIT")
            return True
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def fill_sell(self, order_id: int, market_price_paise: int) -> bool:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            now = self.clock.now_iso()
            cur = self.conn.execute(
                "UPDATE pending_orders SET status = 'filled', updated_at = ? WHERE id = ? AND status = 'pending'",
                (now, order_id),
            )
            if cur.rowcount == 0:
                self.conn.execute("ROLLBACK")
                return False
            order = self.conn.execute("SELECT * FROM pending_orders WHERE id = ?", (order_id,)).fetchone()
            position = self._get_open_position(order["agent_id"], order["ticker"])
            if position is None:
                raise AssertionError(f"SELL order {order_id} filled but no OPEN position for {order['ticker']}")
            self._close_position_core(position, market_price_paise, "AGENT_SELL", order_id, now)
            self.conn.execute("COMMIT")
            return True
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def close_position(self, position_id: int, market_price_paise: int, exit_reason: str) -> bool:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            now = self.clock.now_iso()
            position = self.conn.execute(
                "SELECT * FROM positions WHERE id = ? AND status = 'OPEN'", (position_id,)
            ).fetchone()
            if position is None:
                self.conn.execute("ROLLBACK")
                return False
            self._close_position_core(position, market_price_paise, exit_reason, None, now)
            self.conn.execute("COMMIT")
            return True
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def _close_position_core(self, position, market_price_paise: int, exit_reason: str,
                              order_id: Optional[int], now: str) -> None:
        fill_price = apply_slippage(market_price_paise, "SELL")
        charges = compute_transaction_charges_paise(fill_price, position["shares"], "SELL")
        proceeds = position["shares"] * fill_price - charges

        self.conn.execute(
            "INSERT INTO fills (order_id, position_id, agent_id, ticker, side, shares, "
            "price_paise, charges_paise, executed_at) VALUES (?, ?, ?, ?, 'SELL', ?, ?, ?, ?)",
            (order_id, position["id"], position["agent_id"], position["ticker"], position["shares"], fill_price, charges, now),
        )
        self.conn.execute(
            "UPDATE agents SET cash_paise = cash_paise + ?, updated_at = ? WHERE id = ?",
            (proceeds, now, position["agent_id"]),
        )

        buy_charges_total = self.conn.execute(
            "SELECT COALESCE(SUM(charges_paise), 0) AS total FROM fills WHERE position_id = ? AND side = 'BUY'",
            (position["id"],),
        ).fetchone()["total"]
        cost_basis = position["avg_entry_price_paise"] * position["shares"] + buy_charges_total
        realized_pnl_paise = proceeds - cost_basis
        realized_pnl_pct = (realized_pnl_paise / cost_basis * 100) if cost_basis else 0.0

        entry_date = date.fromisoformat(position["entry_date"])
        exit_date = self.clock.today()
        hold_days = self._trading_days_between(entry_date, exit_date)

        self.conn.execute(
            """
            UPDATE positions SET status = 'CLOSED', exit_date = ?, exit_price_paise = ?,
                exit_reason = ?, hold_days = ?, realized_pnl_paise = ?, realized_pnl_pct = ?,
                last_price_paise = ?
            WHERE id = ?
            """,
            (exit_date.isoformat(), fill_price, exit_reason, hold_days, realized_pnl_paise,
             realized_pnl_pct, fill_price, position["id"]),
        )
        # A stop-hit (or any other close) cancels a still-pending agent SELL for the same ticker.
        self.conn.execute(
            "UPDATE pending_orders SET status = 'cancelled', updated_at = ? "
            "WHERE agent_id = ? AND ticker = ? AND side = 'SELL' AND status = 'pending'",
            (now, position["agent_id"], position["ticker"]),
        )

        event_type = "STOP_HIT" if exit_reason == "STOP_HIT" else "SELL_FILLED"
        self._log_activity(
            position["agent_id"], event_type, position["ticker"],
            f"Closed {position['shares']} {position['ticker']} @ {fill_price}, pnl={realized_pnl_paise}",
            {"position_id": position["id"], "exit_reason": exit_reason,
             "realized_pnl_paise": realized_pnl_paise, "realized_pnl_pct": round(realized_pnl_pct, 4)},
        )
        self.on_position_closed(position["id"])

    def on_position_closed(self, position_id: int) -> None:
        """Stub hook: forensics (week 3) will classify the close here. For now, just logs."""
        logger.info("Position %s closed; forensics not implemented yet.", position_id)

    def _trading_days_between(self, start: date, end: date) -> int:
        if end <= start:
            return 0
        count = 0
        current = start
        while current < end:
            current = next_trading_day(self.conn, current)
            count += 1
        return count

    # --- cancellation --------------------------------------------------------------------------------------

    def cancel_order(self, order_id: int, reason: str) -> bool:
        now = self.clock.now_iso()
        cur = self.conn.execute(
            "UPDATE pending_orders SET status = 'cancelled', rejection_reason = ?, updated_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (reason, now, order_id),
        )
        if cur.rowcount == 0:
            return False
        order = self.conn.execute(
            "SELECT agent_id, ticker FROM pending_orders WHERE id = ?", (order_id,)
        ).fetchone()
        event_type = "ORDER_EXPIRED" if reason == "EXPIRED" else "ORDER_CANCELLED"
        self._log_activity(
            order["agent_id"], event_type, order["ticker"], f"Order {order_id} cancelled: {reason}",
            {"order_id": order_id, "reason": reason},
        )
        return True

    def cancel_pending_for_run(self, agent_id: str, run_date: str) -> int:
        """Cancels every still-pending order whose decision belongs to (agent_id, run_date).
        Used by agents/runner.py's --force path before it regenerates decisions."""
        rows = self.conn.execute(
            """
            SELECT po.id FROM pending_orders po
            JOIN decisions d ON d.id = po.decision_id
            WHERE po.agent_id = ? AND d.run_date = ? AND po.status = 'pending'
            """,
            (agent_id, run_date),
        ).fetchall()
        return sum(1 for row in rows if self.cancel_order(row["id"], "RUN_FORCE_CANCELLED"))
