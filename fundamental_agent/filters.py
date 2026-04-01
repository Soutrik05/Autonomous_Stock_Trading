# ============================================================
# fundamental_agent/filters.py
#
# Hard disqualification filters applied before scoring.
# A stock that fails any hard filter is excluded from scoring
# entirely — it does not receive a score and is not passed to
# the orchestrator.
#
# Hard filters are intentionally blunt. They remove stocks that
# are structurally broken or too risky regardless of any
# compensating factors. Scoring nuance is irrelevant for these.
#
# Single public function: apply_hard_filters(raw) -> str | None
#   Returns a disqualification reason string if the stock fails,
#   or None if the stock passes all filters.
# ============================================================

import logging
from typing import Any, Dict, Optional

from fundamental_agent import config as cfg

logger = logging.getLogger("fundamental_agent.filters")


def apply_hard_filters(raw: Dict[str, Any]) -> Optional[str]:
    """
    Applies hard disqualification rules in priority order.
    Returns the first failure reason found, or None if all pass.

    Rules:
        1. D/E > max_debt_equity (2.5x default):
               Too leveraged to be investable under Varsity criteria.
               Exception: Financial Services sector is fully exempt.
               Banks and NBFCs borrow to lend — D/E=3x is healthy
               for Bajaj Finance, normal for HDFC Bank. Screener.in
               doesn't even display D/E for banks for this reason.

        2. Consecutive negative EPS quarters >= threshold (2 default):
               Two or more back-to-back loss quarters signals
               operational distress, not a one-off blip.

        3. ROE < min_roe (0.0 default — i.e. negative ROE):
               Negative ROE means the company is destroying shareholder
               value. Even distressed turnarounds should show improving
               (not negative) ROE to be considered investable.

    Args:
        raw: Output dict from fetcher.fetch_stock_data().

    Returns:
        A human-readable disqualification reason string on failure.
        None if the stock passes all hard filters.
    """
    sector = raw.get("sector", "")

    # ── Rule 1: D/E cap ──────────────────────────────────────
    de = raw.get("de")
    if de is not None and de > cfg.HARD_FILTERS["max_debt_equity"]:
        if sector == "Financial Services":
            logger.debug(
                f"D/E {de:.2f}x exceeds cap but sector=Financial Services "
                f"— exempt from D/E hard filter"
            )
        else:
            return f"D/E {de:.2f}x exceeds maximum {cfg.HARD_FILTERS['max_debt_equity']}x"

    # ── Rule 2: Consecutive negative EPS quarters ────────────
    neg_q = raw.get("negative_eps_quarters", 0)
    if neg_q >= cfg.HARD_FILTERS["min_negative_eps_quarters"]:
        return f"EPS negative for {neg_q} consecutive quarters"

    # ── Rule 3: Negative ROE ─────────────────────────────────
    roe = raw.get("roe")
    if roe is not None and roe < cfg.HARD_FILTERS["min_roe"]:
        return f"ROE {roe * 100:.1f}% is negative"

    return None   # all filters passed
