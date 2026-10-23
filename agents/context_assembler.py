"""
Builds compact numeric candidate rows and enforces the prompt token budget and trim order.
See Plan_v3 §3.2.
"""
import sqlite3
from typing import Dict, List, Optional, Tuple

from core.features import persona_allowed_metric_names
from settings import settings

# Recalibrated against a real measured Groq call (day 3c): real chars/token was ~2.64 on this
# prompt style; 3.5 (generic prose) undershot real tokens_in by ~25%. PROMPT_TOKEN_TARGET and
# PROMPT_TOKEN_CEILING themselves are unchanged -- only this estimator divisor moved.
CHARS_PER_TOKEN = 2.7

# Shown once in the REGIME line, never repeated per candidate row.
_REGIME_LEVEL_NAMES = {"india_vix", "regime"}


def estimate_tokens(text: str) -> int:
    """First-pass token estimate: characters / CHARS_PER_TOKEN."""
    return int(len(text) / CHARS_PER_TOKEN)


def _abbrev_sector(sector: Optional[str]) -> str:
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


def build_candidate_row(ticker: str, sector: str, features: dict, is_held: bool, allowed_names: List[str]) -> str:
    """One compact row per candidate, keyed by the EXACT FeatureSnapshot names in
    `allowed_names` (see core.features.persona_allowed_metric_names) -- e.g. close=, ema_20=,
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


def build_regime_line(india_vix: Optional[float], regime: Optional[str]) -> str:
    if regime is None:
        return "REGIME: unknown (macro data not yet available for this date)."
    vix_part = "NA" if india_vix is None else f"{india_vix:.2f}"
    return f"REGIME: {regime} (India VIX: {vix_part})."


def build_heuristics_block(heuristics: List[dict]) -> str:
    if not heuristics:
        return "ACTIVE HEURISTICS: none yet."
    lines = ["ACTIVE HEURISTICS:"]
    for h in heuristics:
        lines.append(f"- [{h['kind']}] {h['heuristic_text']} (confidence {h['confidence']:.2f})")
    return "\n".join(lines)


def build_episodic_memory_block(closed_positions: List[dict]) -> str:
    if not closed_positions:
        return "RECENT CLOSED TRADES: none yet."
    lines = ["RECENT CLOSED TRADES (most recent first):"]
    for p in closed_positions[: settings.EPISODIC_MEMORY_LIMIT]:
        excerpt = (p.get("entry_reasoning") or "")[:80]
        pnl = p.get("realized_pnl_pct")
        pnl_text = "NA" if pnl is None else f"{pnl:.1f}%"
        lines.append(
            f"- {p['ticker']}: entered because \"{excerpt}\", exited {p.get('exit_reason')} "
            f"after {p.get('hold_days')}d, pnl={pnl_text}"
        )
    return "\n".join(lines)


def build_portfolio_state_block(cash_paise: int, holdings: List[dict]) -> str:
    cash_rupees = cash_paise / 100
    if not holdings:
        return f"PORTFOLIO: cash=Rs{cash_rupees:,.0f}, no open positions."
    account_value_paise = cash_paise + sum(h["value_paise"] for h in holdings)
    sector_value: Dict[str, int] = {}
    for h in holdings:
        sector_value[h["sector"]] = sector_value.get(h["sector"], 0) + h["value_paise"]

    holdings_text = ", ".join(f"{h['ticker']}x{h['shares']}" for h in holdings)
    sector_text = ", ".join(
        f"{sector}={value / account_value_paise * 100:.0f}%" for sector, value in sector_value.items()
    )
    return f"PORTFOLIO: cash=Rs{cash_rupees:,.0f}\nHoldings: {holdings_text}\nSector exposure: {sector_text}"


def assemble_prompt(
    system_prompt: str,
    regime_line: str,
    heuristics_block: str,
    episodic_block: str,
    portfolio_block: str,
    candidates: List[dict],
    allowed_names: List[str],
    rag_block: Optional[str] = None,
    ceiling: Optional[int] = None,
) -> Tuple[str, dict]:
    """Assembles the user-prompt body from the blocks above plus one row per candidate
    ({"ticker", "sector", "features", "is_held", "intensity_score"}), trimming to `ceiling`
    (default settings.PROMPT_TOKEN_CEILING) if needed, in order: drop RAG, drop episodic memory,
    drop the lowest-intensity watchlist (non-held) candidates. Open positions are never trimmed.
    `allowed_names` (from core.features.persona_allowed_metric_names) decides which keys each
    candidate row shows. Returns (user_prompt_text, trim_debug_info)."""
    ceiling = settings.PROMPT_TOKEN_CEILING if ceiling is None else ceiling
    held = [c for c in candidates if c["is_held"]]
    not_held = sorted((c for c in candidates if not c["is_held"]), key=lambda c: c.get("intensity_score") or 0)

    trimmed = {"rag": False, "episodic": False, "dropped_candidates": []}

    def render() -> str:
        rows = [
            build_candidate_row(c["ticker"], c["sector"], c["features"], c["is_held"], allowed_names)
            for c in held + not_held
        ]
        blocks = [regime_line, heuristics_block, episodic_block, portfolio_block]
        if rag_block:
            blocks.append(rag_block)
        blocks.append("CANDIDATES:\n" + "\n".join(rows))
        return "\n\n".join(blocks)

    def over_budget() -> bool:
        return estimate_tokens(system_prompt) + estimate_tokens(render()) > ceiling

    if not over_budget():
        return render(), trimmed

    if rag_block:
        rag_block = None
        trimmed["rag"] = True
        if not over_budget():
            return render(), trimmed

    if episodic_block and episodic_block != "RECENT CLOSED TRADES: none yet.":
        episodic_block = "RECENT CLOSED TRADES: trimmed for token budget."
        trimmed["episodic"] = True
        if not over_budget():
            return render(), trimmed

    while not_held and over_budget():
        dropped = not_held.pop(0)  # lowest intensity first (ascending sort)
        trimmed["dropped_candidates"].append(dropped["ticker"])

    return render(), trimmed


# --- DB-backed helpers that pull the blocks' raw data (used by agents/runner.py) ----------------

def load_portfolio_state(conn: sqlite3.Connection, agent_id: str) -> Tuple[int, List[dict]]:
    agent_row = conn.execute("SELECT cash_paise FROM agents WHERE id = ?", (agent_id,)).fetchone()
    cash_paise = agent_row["cash_paise"] if agent_row else 0
    rows = conn.execute(
        "SELECT ticker, sector, shares, avg_entry_price_paise, last_price_paise FROM positions "
        "WHERE agent_id = ? AND status = 'OPEN'",
        (agent_id,),
    ).fetchall()
    holdings = [
        {
            "ticker": r["ticker"],
            "sector": r["sector"],
            "shares": r["shares"],
            "value_paise": r["shares"] * r["last_price_paise"],
        }
        for r in rows
    ]
    return cash_paise, holdings


def load_active_heuristics(conn: sqlite3.Connection, agent_id: str) -> List[dict]:
    rows = conn.execute(
        "SELECT kind, heuristic_text, confidence FROM agent_memory "
        "WHERE agent_id = ? AND status IN ('active', 'reinforced') "
        "ORDER BY confidence DESC LIMIT ?",
        (agent_id, settings.MAX_ACTIVE_HEURISTICS_IN_PROMPT),
    ).fetchall()
    return [dict(r) for r in rows]


def load_episodic_memory(conn: sqlite3.Connection, agent_id: str) -> List[dict]:
    rows = conn.execute(
        "SELECT ticker, entry_reasoning, exit_reason, hold_days, realized_pnl_pct FROM positions "
        "WHERE agent_id = ? AND status = 'CLOSED' ORDER BY exit_date DESC LIMIT ?",
        (agent_id, settings.EPISODIC_MEMORY_LIMIT),
    ).fetchall()
    return [dict(r) for r in rows]


def extract_regime(features_by_ticker: Dict[str, dict]) -> Tuple[Optional[float], Optional[str]]:
    for features in features_by_ticker.values():
        if features.get("regime") is not None:
            return features.get("india_vix"), features.get("regime")
    return None, None


def build_user_prompt(
    portfolio_conn: sqlite3.Connection, agent_id: str, review_pool: List[dict],
    features_by_ticker: Dict[str, dict], sector_by_ticker: Dict[str, str],
    intensity_by_ticker: Dict[str, float], system_prompt: str, technical_hurdles: dict,
    fundamental_hurdles: dict, rag_block: Optional[str] = None,
) -> Tuple[str, dict]:
    """End-to-end: pulls portfolio/heuristics/episodic-memory data and assembles the full user
    prompt for one agent's nightly run. `technical_hurdles`/`fundamental_hurdles` (the
    persona's) decide the candidate rows' field set via persona_allowed_metric_names().
    Returns (user_prompt_text, trim_debug_info)."""
    cash_paise, holdings = load_portfolio_state(portfolio_conn, agent_id)
    heuristics = load_active_heuristics(portfolio_conn, agent_id)
    closed_positions = load_episodic_memory(portfolio_conn, agent_id)
    india_vix, regime = extract_regime(features_by_ticker)
    allowed_names = persona_allowed_metric_names(technical_hurdles, fundamental_hurdles)

    candidates = [
        {
            "ticker": entry["ticker"],
            "sector": sector_by_ticker.get(entry["ticker"], "UNK"),
            "features": features_by_ticker.get(entry["ticker"], {}),
            "is_held": entry["is_held"],
            "intensity_score": intensity_by_ticker.get(entry["ticker"]),
        }
        for entry in review_pool
    ]

    return assemble_prompt(
        system_prompt=system_prompt,
        regime_line=build_regime_line(india_vix, regime),
        heuristics_block=build_heuristics_block(heuristics),
        episodic_block=build_episodic_memory_block(closed_positions),
        portfolio_block=build_portfolio_state_block(cash_paise, holdings),
        candidates=candidates,
        allowed_names=allowed_names,
        rag_block=rag_block,
    )
