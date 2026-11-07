"""
Builds compact numeric candidate rows and enforces the prompt token budget and trim order.
See Plan_v3 §3.2.
"""

import sqlite3
from typing import Any

from core.config import settings
from features.contracts import persona_allowed_metric_names

# Recalibrated against a real measured Groq call (day 3c): real chars/token was ~2.64 on this
# prompt style; 3.5 (generic prose) undershot real tokens_in by ~25%. PROMPT_TOKEN_TARGET and
# PROMPT_TOKEN_CEILING themselves are unchanged -- only this estimator divisor moved.
CHARS_PER_TOKEN = 2.7

# Shown once in the REGIME line, never repeated per candidate row.
_REGIME_LEVEL_NAMES = {"india_vix", "regime"}


def estimate_tokens(text: str) -> int:
    """First-pass token estimate: characters / CHARS_PER_TOKEN."""
    return int(len(text) / CHARS_PER_TOKEN)


def _abbrev_sector(sector: str | None) -> str:
    return (sector or "UNK")[:3].upper()


def _fmt_value(name: str, value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if name == "macd_hist":
        return f"{value:+.2f}"
    if name in ("rsi_14", "adx_14", "dist_52w_high_pct", "dist_52w_low_pct"):
        return f"{value:.1f}"
    return f"{value:.2f}"


def build_candidate_row(ticker: str, sector: str, features: dict, is_held: bool, allowed_names: list[str]) -> str:
    """One compact row per candidate, keyed by the EXACT FeatureSnapshot names in
    `allowed_names` (see features.contracts.persona_allowed_metric_names) -- e.g. close=, ema_20=,
    rsi_14=, macd_hist=. A field whose value is None is omitted entirely, not shown as NA."""
    parts = [ticker, _abbrev_sector(sector)]
    for name in allowed_names:
        if name in _REGIME_LEVEL_NAMES:
            continue
        value = features.get(name)
        if value is None:
            continue
        parts.append(f"{name}={_fmt_value(name, value)}")
    parts.append(f"pos={'held' if is_held else 'none'}")
    return "|".join(parts)


def build_regime_line(india_vix: float | None, regime: str | None) -> str:
    if regime is None:
        return "REGIME: unknown (macro data not yet available for this date)."
    vix_part = "NA" if india_vix is None else f"{india_vix:.2f}"
    return f"REGIME: {regime} (India VIX: {vix_part})."


def build_heuristics_block(heuristics: list[dict]) -> str:
    if not heuristics:
        return "ACTIVE HEURISTICS: none yet."
    lines = ["ACTIVE HEURISTICS:"]
    for h in heuristics:
        ctx = h.get("context") or "ENTRY"
        lines.append(f"- [{ctx} {h['kind']}] {h['heuristic_text']} (confidence {h['confidence']:.2f})")
    return "\n".join(lines)


def build_episodic_memory_block(closed_positions: list[dict]) -> str:
    if not closed_positions:
        return "RECENT CLOSED TRADES: none yet."
    lines = ["RECENT CLOSED TRADES (most recent first):"]
    for p in closed_positions[: settings.EPISODIC_MEMORY_LIMIT]:
        excerpt = (p.get("entry_reasoning") or "")[:80]
        pnl = p.get("realized_pnl_pct")
        pnl_text = "NA" if pnl is None else f"{pnl:.1f}%"
        lines.append(
            f'- {p["ticker"]}: entered because "{excerpt}", exited {p.get("exit_reason")} '
            f"after {p.get('hold_days')}d, pnl={pnl_text}"
        )
    return "\n".join(lines)


def compute_kelly_recommendation(conn: sqlite3.Connection, agent_id: str) -> dict | None:
    """Computes empirical Half-Kelly fraction from closed positions if at least 10 trades exist."""
    rows = conn.execute(
        "SELECT realized_pnl_pct FROM positions WHERE agent_id = ? AND status = 'CLOSED'",
        (agent_id,),
    ).fetchall()
    pnls = [r[0] for r in rows if r[0] is not None]
    if len(pnls) < 10:
        return {"trades": len(pnls)}
    wins = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]
    win_rate = len(wins) / len(pnls)
    if not losses or not wins:
        return {"trades": len(pnls)}
    avg_win = sum(wins) / len(wins)
    avg_loss = sum(losses) / len(losses)
    if avg_loss <= 0:
        return {"trades": len(pnls)}
    payoff = avg_win / avg_loss
    kelly = win_rate - ((1.0 - win_rate) / payoff)
    half_kelly = 0.5 * kelly
    recommended_risk_pct = round(max(1.0, min(2.0, half_kelly * 100.0)), 2)
    return {
        "trades": len(pnls),
        "win_rate": round(win_rate * 100.0, 1),
        "payoff_ratio": round(payoff, 2),
        "half_kelly_pct": round(half_kelly * 100.0, 2),
        "recommended_risk_pct": recommended_risk_pct,
    }


def build_portfolio_state_block(cash_paise: int, holdings: list[dict], kelly_context: dict | None = None) -> str:
    cash_rupees = cash_paise / 100
    account_value_paise = cash_paise + sum(h["value_paise"] for h in holdings)
    lines = [f"PORTFOLIO: cash=Rs{cash_rupees:,.0f}"]
    if holdings:
        holdings_text = ", ".join(f"{h['ticker']}x{h['shares']}" for h in holdings)
        sector_value: dict[str, int] = {}
        for h in holdings:
            sector_value[h["sector"]] = sector_value.get(h["sector"], 0) + h["value_paise"]
        sector_text = ", ".join(
            f"{sector}={value / account_value_paise * 100:.0f}%" for sector, value in sector_value.items()
        )
        lines.append(f"Holdings: {holdings_text}")
        lines.append(f"Sector exposure: {sector_text}")

        # Check for TARGET_REACHED alerts today
        target_alerts = [h for h in holdings if h.get("target_reached")]
        for ta in target_alerts:
            t_rupees = (ta.get("target_paise") or 0) / 100.0
            lines.append(
                f"TARGET ALERT: {ta['ticker']} reached profit target (Rs{t_rupees:.2f}) today! "
                f"Action required: deliberate whether to SELL (take profit tomorrow morning), "
                f"ADJUST (ratchet stop up and raise target), or HOLD."
            )
    else:
        lines[0] += ", no open positions."

    if kelly_context:
        if kelly_context.get("trades", 0) >= 10 and "recommended_risk_pct" in kelly_context:
            lines.append(
                f"Kelly Sizing (Module 9): Empirical win rate {kelly_context['win_rate']}%, "
                f"payoff {kelly_context['payoff_ratio']} over {kelly_context['trades']} closed trades "
                f"-> Half-Kelly suggests {kelly_context['recommended_risk_pct']}% capital risk budget per trade."
            )
        else:
            lines.append(
                f"Kelly Sizing (Module 9): Closed trades ({kelly_context.get('trades', 0)}) < 10 "
                f"(insufficient sample); adhere to textbook 2.0% risk rule per trade."
            )
    return "\n".join(lines)


def build_headlines_block(candidates: list[dict]) -> str:
    """Builds a compact summary of top recent headlines with relative age and FinBERT score."""
    from core.schemas import sanitize_text_for_prompt

    lines = []
    for c in candidates:
        headlines = c.get("headlines") or []
        if not headlines:
            continue
        art_lines = []
        for h in headlines[:3]:
            rel_age = h.get("relative_age") or "recent"
            score = h.get("sentiment_score")
            score_str = f"{score:+.2f}" if score is not None else "0.00"
            heading = sanitize_text_for_prompt(h.get("heading") or "", max_len=120)
            art_lines.append(f"  • [{rel_age} | score: {score_str}] {heading}")
        if art_lines:
            lines.append(f"{c['ticker']}:\n" + "\n".join(art_lines))
    if not lines:
        return ""
    return "RECENT HEADLINES:\n" + "\n".join(lines)


def assemble_prompt(
    system_prompt: str,
    regime_line: str,
    heuristics_block: str,
    episodic_block: str,
    portfolio_block: str,
    candidates: list[dict],
    allowed_names: list[str],
    ceiling: int | None = None,
) -> tuple[str, dict]:
    """Assembles the user-prompt body from the blocks above plus one row per candidate
    ({"ticker", "sector", "features", "is_held", "intensity_score", "headlines"}), trimming to `ceiling`
    (default settings.PROMPT_TOKEN_CEILING) if needed, in order: drop episodic memory,
    drop headlines, drop the lowest-intensity watchlist (non-held) candidates. Open positions are never trimmed.
    `allowed_names` (from features.contracts.persona_allowed_metric_names) decides which keys each
    candidate row shows. Returns (user_prompt_text, trim_debug_info)."""
    ceiling = settings.PROMPT_TOKEN_CEILING if ceiling is None else ceiling
    held = [c for c in candidates if c["is_held"]]
    not_held = sorted((c for c in candidates if not c["is_held"]), key=lambda c: c.get("intensity_score") or 0)

    trimmed: dict[str, Any] = {"episodic": False, "headlines": False, "dropped_candidates": []}

    def render(include_headlines: bool = True) -> str:
        rows = [
            build_candidate_row(c["ticker"], c["sector"], c["features"], c["is_held"], allowed_names)
            for c in held + not_held
        ]
        blocks = [regime_line, heuristics_block, episodic_block, portfolio_block]
        blocks.append("CANDIDATES:\n" + "\n".join(rows))
        if include_headlines:
            headlines_str = build_headlines_block(held + not_held)
            if headlines_str:
                blocks.append(headlines_str)
        return "\n\n".join(blocks)

    def over_budget(include_headlines: bool = True) -> bool:
        return estimate_tokens(system_prompt) + estimate_tokens(render(include_headlines)) > ceiling

    if not over_budget(include_headlines=True):
        return render(include_headlines=True), trimmed

    if episodic_block and episodic_block != "RECENT CLOSED TRADES: none yet.":
        episodic_block = "RECENT CLOSED TRADES: trimmed for token budget."
        trimmed["episodic"] = True
        if not over_budget(include_headlines=True):
            return render(include_headlines=True), trimmed

    if over_budget(include_headlines=True):
        trimmed["headlines"] = True
        if not over_budget(include_headlines=False):
            return render(include_headlines=False), trimmed

    while not_held and over_budget(include_headlines=False):
        dropped = not_held.pop(0)  # lowest intensity first (ascending sort)
        trimmed["dropped_candidates"].append(dropped["ticker"])

    return render(include_headlines=False), trimmed


# --- DB-backed helpers that pull the blocks' raw data (used by agents/runner.py) ----------------


def load_portfolio_state(conn: sqlite3.Connection, agent_id: str) -> tuple[int, list[dict]]:
    agent_row = conn.execute("SELECT cash_paise FROM agents WHERE id = ?", (agent_id,)).fetchone()
    cash_paise = agent_row["cash_paise"] if agent_row else 0
    rows = conn.execute(
        "SELECT ticker, sector, shares, avg_entry_price_paise, last_price_paise, stop_paise, target_paise FROM positions "
        "WHERE agent_id = ? AND status = 'OPEN'",
        (agent_id,),
    ).fetchall()

    target_alerts = set()
    try:
        latest_act = conn.execute("SELECT MAX(created_at) FROM activity_log").fetchone()
        if latest_act and latest_act[0]:
            today_prefix = str(latest_act[0])[:10]
            t_rows = conn.execute(
                "SELECT ticker FROM activity_log WHERE agent_id = ? AND event_type = 'TARGET_REACHED' AND created_at LIKE ?",
                (agent_id, f"{today_prefix}%"),
            ).fetchall()
            target_alerts = {r["ticker"] if isinstance(r, sqlite3.Row) else r[0] for r in t_rows}
    except Exception:
        pass

    holdings = [
        {
            "ticker": r["ticker"],
            "sector": r["sector"],
            "shares": r["shares"],
            "value_paise": r["shares"] * r["last_price_paise"],
            "target_reached": r["ticker"] in target_alerts,
            "target_paise": r["target_paise"],
            "stop_paise": r["stop_paise"],
        }
        for r in rows
    ]
    return cash_paise, holdings


def load_active_heuristics(conn: sqlite3.Connection, agent_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT kind, context, heuristic_text, confidence FROM agent_memory "
        "WHERE agent_id = ? AND status IN ('active', 'reinforced') "
        "ORDER BY confidence DESC LIMIT ?",
        (agent_id, settings.MAX_ACTIVE_HEURISTICS_IN_PROMPT),
    ).fetchall()
    return [dict(r) for r in rows]


def load_episodic_memory(conn: sqlite3.Connection, agent_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT ticker, entry_reasoning, exit_reason, hold_days, realized_pnl_pct FROM positions "
        "WHERE agent_id = ? AND status = 'CLOSED' ORDER BY exit_date DESC LIMIT ?",
        (agent_id, settings.EPISODIC_MEMORY_LIMIT),
    ).fetchall()
    return [dict(r) for r in rows]


def extract_regime(features_by_ticker: dict[str, dict]) -> tuple[float | None, str | None]:
    for features in features_by_ticker.values():
        if features.get("regime") is not None:
            return features.get("india_vix"), features.get("regime")
    return None, None


def build_user_prompt(
    portfolio_conn: sqlite3.Connection,
    agent_id: str,
    review_pool: list[dict],
    features_by_ticker: dict[str, dict],
    sector_by_ticker: dict[str, str],
    intensity_by_ticker: dict[str, float],
    system_prompt: str,
    technical_hurdles: dict,
    fundamental_hurdles: dict,
    news_conn: sqlite3.Connection | None = None,
    news_lookback_days: int = 7,
    run_date: str | None = None,
    extra_metrics: list[str] | None = None,
) -> tuple[str, dict]:
    """End-to-end: pulls portfolio/heuristics/episodic-memory data and assembles the full user
    prompt for one agent's nightly run. `technical_hurdles`/`fundamental_hurdles` (the
    persona's) decide the candidate rows' field set via persona_allowed_metric_names().
    Also queries data/news.db for the persona's news_lookback_days to attach top 3 headlines
    with relative timestamps and FinBERT scores.
    Returns (user_prompt_text, trim_debug_info)."""
    cash_paise, holdings = load_portfolio_state(portfolio_conn, agent_id)
    heuristics = load_active_heuristics(portfolio_conn, agent_id)
    closed_positions = load_episodic_memory(portfolio_conn, agent_id)
    india_vix, regime = extract_regime(features_by_ticker)
    extras = list(extra_metrics or [])
    if news_lookback_days > 0 and "news_sentiment" not in extras:
        extras.append("news_sentiment")
    allowed_names = persona_allowed_metric_names(technical_hurdles, fundamental_hurdles, extra_metrics=extras)

    owns_news = False
    if news_conn is None and run_date:
        try:
            from core.database import get_connection

            news_conn = get_connection(settings.NEWS_DB_PATH)
            owns_news = True
        except Exception:
            news_conn = None

    headlines_by_ticker = {}
    if news_conn is not None and run_date:
        try:
            from ingestion.sync_news import get_ticker_news_sentiment

            for entry in review_pool:
                _, _, arts = get_ticker_news_sentiment(
                    news_conn, entry["ticker"], run_date, lookback_days=news_lookback_days
                )
                if arts:
                    headlines_by_ticker[entry["ticker"]] = arts
        except Exception:
            pass
        finally:
            if owns_news:
                news_conn.close()

    candidates = [
        {
            "ticker": entry["ticker"],
            "sector": sector_by_ticker.get(entry["ticker"], "UNK"),
            "features": features_by_ticker.get(entry["ticker"], {}),
            "is_held": entry["is_held"],
            "intensity_score": intensity_by_ticker.get(entry["ticker"]),
            "headlines": headlines_by_ticker.get(entry["ticker"], []),
        }
        for entry in review_pool
    ]

    kelly_context = None
    if agent_id in ("varsity", "stockminds-core"):
        try:
            kelly_context = compute_kelly_recommendation(portfolio_conn, agent_id)
        except Exception:
            pass

    return assemble_prompt(
        system_prompt=system_prompt,
        regime_line=build_regime_line(india_vix, regime),
        heuristics_block=build_heuristics_block(heuristics),
        episodic_block=build_episodic_memory_block(closed_positions),
        portfolio_block=build_portfolio_state_block(cash_paise, holdings, kelly_context=kelly_context),
        candidates=candidates,
        allowed_names=allowed_names,
    )
