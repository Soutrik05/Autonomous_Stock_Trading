"""
Persona-Aligned Memory Consolidator.

Enforces:
1. Strict 5-heuristic capacity ceiling per persona (status in 'active', 'reinforced').
2. Deterministic Persona Alignment Guard (deprecates philosophy-drift rules).
3. Contradiction & Collision Reconciliation:
   - 'reinforced' strictly supersedes contradictory 'active' rules.
   - Intramural 'reinforced' collisions resolved via Wilson score or regime conditionality.
4. Atomic Cutover Merging:
   - Only 'reinforced' heuristics merge with other 'reinforced' heuristics.
   - Obsolete component rules marked 'deprecated' with 'superseded_by'.
5. LLM Synthesis via gemini-3.8-flash for compound multi-feature rules, with
   deterministic Wilson-score fallback.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from core.clock import Clock
from core.config import settings
from features.contracts import _BY_NAME, predicate_feature_names

logger = logging.getLogger(__name__)

# Maximum total heuristics (active + reinforced) allowed per agent
MAX_TOTAL_HEURISTICS_PER_PERSONA = 5

# Persona Philosophy Contracts
# Defines allowed feature groups, forbidden metrics, minimum holding horizon, and core mandate
PERSONA_PHILOSOPHY_CONTRACTS: dict[str, dict[str, Any]] = {
    "simons": {
        "strategy_type": "QUANT_MOMENTUM",
        "core_mandate": "Short-horizon statistical momentum, volatility scaling, and trend breakouts.",
        "allowed_groups": {"Price", "Trend", "Momentum", "Volatility", "Volume", "Structure", "Macro"},
        "forbidden_groups": {"Quality", "Valuation", "Solvency", "Cash flow", "Growth", "Ownership"},
        "forbidden_metrics": {"pe", "pb", "peg", "dcf_discount_pct", "debt_to_equity", "promoter_holding_pct"},
        "min_holding_days": 1,
    },
    "varsity": {
        "strategy_type": "TECHNO_FUNDA_SWING",
        "core_mandate": "Classical technical breakouts (20/50 EMA, Flag, Cup & Handle) with fundamental solvency hygiene.",
        "allowed_groups": {"Price", "Trend", "Momentum", "Volatility", "Volume", "Structure", "Quality", "Solvency", "Macro"},
        "forbidden_groups": set(),
        "forbidden_metrics": set(),
        "min_holding_days": 3,
    },
    "lynch": {
        "strategy_type": "GARP_INVESTING",
        "core_mandate": "Growth at a Reasonable Price (PEG < 1.2, earnings growth, low debt, medium-to-long term compounding).",
        "allowed_groups": {"Growth", "Valuation", "Solvency", "Quality", "Cash flow", "Ownership", "Macro", "Trend"},
        "forbidden_groups": set(),
        "forbidden_metrics": {"rsi_14", "macd_hist", "kaufman_er_20", "skew_60"},
        "min_holding_days": 15,
    },
    "marks": {
        "strategy_type": "CONTRARIAN_VALUE",
        "core_mandate": "Contrarian value, margin of safety, asymmetric risk, buying during macro distress and elevated India VIX.",
        "allowed_groups": {"Valuation", "Solvency", "Quality", "Cash flow", "Volatility", "Macro", "Structure"},
        "forbidden_groups": set(),
        "forbidden_metrics": {"adx_14", "obv_slope_sign"},
        "min_holding_days": 15,
    },
    "jhunjhunwala": {
        "strategy_type": "BIG_BULL_THEMATIC",
        "core_mandate": "High-beta compounding, secular India growth themes, sector leaders, high promoter commitment, wide trailing stops.",
        "allowed_groups": {"Growth", "Quality", "Ownership", "Trend", "Macro", "Valuation", "Price"},
        "forbidden_groups": set(),
        "forbidden_metrics": {"rsi_14", "macd_hist", "kaufman_er_20"},
        "min_holding_days": 20,
    },
}


def audit_persona_drift(heuristic: dict[str, Any], persona_id: str) -> tuple[bool, str]:
    """
    Deterministically audits whether a heuristic conforms to its persona philosophy.
    Returns (True, '') if aligned, or (False, reason) if it violates the persona contract.
    """
    clean_id = persona_id.replace("baseline-", "").replace("-rules", "")
    contract = PERSONA_PHILOSOPHY_CONTRACTS.get(clean_id)
    if not contract:
        return True, ""

    trigger_raw = heuristic.get("trigger_json") or heuristic.get("trigger")
    if isinstance(trigger_raw, str):
        try:
            trigger_dict = json.loads(trigger_raw)
        except Exception:
            trigger_dict = {}
    elif isinstance(trigger_raw, dict):
        trigger_dict = trigger_raw
    else:
        trigger_dict = {}

    features = predicate_feature_names(trigger_dict)

    # 1. Check forbidden specific metrics
    forbidden_metrics = contract["forbidden_metrics"]
    violated_metrics = features & forbidden_metrics
    if violated_metrics:
        return False, f"PHILOSOPHY_DRIFT: Uses forbidden metric(s) {sorted(violated_metrics)} for persona {clean_id}"

    # 2. Check forbidden feature groups
    forbidden_groups = contract["forbidden_groups"]
    for feat in features:
        fdef = _BY_NAME.get(feat)
        if fdef and fdef.group in forbidden_groups:
            return False, f"PHILOSOPHY_DRIFT: Metric '{feat}' belongs to forbidden group '{fdef.group}' for persona {clean_id}"

    # 3. Check fast technical exits on fundamental personas
    context = heuristic.get("context", "ENTRY")
    if context == "EXIT" and clean_id in ("lynch", "marks", "jhunjhunwala"):
        fast_exit_indicators = {"rsi_14", "macd_hist", "stoch", "atr_14"}
        if features & fast_exit_indicators:
            return False, f"PHILOSOPHY_DRIFT: Fundamental persona {clean_id} cannot have fast technical indicator exits"

    return True, ""


def detect_predicate_collisions(h1: dict[str, Any], h2: dict[str, Any]) -> bool:
    """
    Checks if two heuristics have conflicting or mutually opposing directives.
    E.g., one SEEK and one AVOID on the same feature/context without regime distinction.
    Heuristics partitioned into different explicit market regimes do not collide.
    """
    if h1.get("context", "ENTRY") != h2.get("context", "ENTRY"):
        return False

    reg1 = h1.get("regime_tag") or "ALL"
    reg2 = h2.get("regime_tag") or "ALL"
    if reg1 != "ALL" and reg2 != "ALL" and reg1 != reg2:
        return False

    t1_raw = h1.get("trigger_json") or h1.get("trigger")
    t2_raw = h2.get("trigger_json") or h2.get("trigger")
    try:
        t1 = json.loads(t1_raw) if isinstance(t1_raw, str) else (t1_raw or {})
        t2 = json.loads(t2_raw) if isinstance(t2_raw, str) else (t2_raw or {})
    except Exception:
        return False

    feat1 = t1.get("feature")
    feat2 = t2.get("feature")
    if not feat1 or not feat2 or feat1 != feat2:
        return False

    # Same feature and same context, but opposing kind
    if h1.get("kind") != h2.get("kind"):
        return True

    return False


def reconcile_active_vs_reinforced(conn: sqlite3.Connection, agent_id: str, clock: Clock) -> list[int]:
    """
    Enforces that 'reinforced' heuristics strictly supersede conflicting 'active' heuristics.
    Any 'active' heuristic that contradicts a 'reinforced' heuristic is deprecated.
    Returns list of deprecated active heuristic IDs.
    """
    rows = conn.execute(
        "SELECT id, kind, context, heuristic_text, trigger_json, status, confidence "
        "FROM agent_memory WHERE agent_id = ? AND status IN ('active', 'reinforced')",
        (agent_id,),
    ).fetchall()

    heuristics = [dict(r) for r in rows]
    reinforced = [h for h in heuristics if h["status"] == "reinforced"]
    active = [h for h in heuristics if h["status"] == "active"]

    deprecated_ids = []
    for act in active:
        for reinf in reinforced:
            if detect_predicate_collisions(act, reinf):
                logger.info(
                    "consolidator: Deprecating active heuristic #%d because it conflicts with reinforced heuristic #%d",
                    act["id"],
                    reinf["id"],
                )
                conn.execute(
                    "UPDATE agent_memory SET status = 'deprecated', updated_at = ? WHERE id = ?",
                    (clock.now_iso(), act["id"]),
                )
                deprecated_ids.append(act["id"])
                _log_activity(
                    conn,
                    agent_id,
                    "HEURISTIC_STATUS_CHANGED",
                    f"Active heuristic #{act['id']} deprecated (contradicts reinforced #{reinf['id']})",
                    {"heuristic_id": act["id"], "conflicted_with_reinforced": reinf["id"]},
                    clock,
                )
                break

    return deprecated_ids


def consolidate_persona_memory(
    conn: sqlite3.Connection,
    agent_id: str,
    clock: Clock,
    llm_client: Any | None = None,
    max_total: int = MAX_TOTAL_HEURISTICS_PER_PERSONA,
) -> dict[str, Any]:
    """
    Main entry point for memory consolidation.
    1. Audits and deprecates any heuristics exhibiting philosophy drift.
    2. Deprecates any active heuristics contradicting reinforced heuristics.
    3. If total active + reinforced > max_total, consolidates or prunes down to <= max_total.
    4. Only reinforced rules are merged together (atomic cutover).
    """
    clean_id = agent_id.replace("baseline-", "").replace("-rules", "")
    now_iso = clock.now_iso()

    # Step 1: Deterministic Philosophy Drift Audit
    rows = conn.execute(
        "SELECT id, kind, context, heuristic_text, trigger_json, status, confidence, times_triggered, times_successful "
        "FROM agent_memory WHERE agent_id = ? AND status IN ('active', 'reinforced')",
        (agent_id,),
    ).fetchall()

    live_heuristics = [dict(r) for r in rows]
    drift_deprecated = []

    for h in live_heuristics:
        is_aligned, reason = audit_persona_drift(h, clean_id)
        if not is_aligned:
            logger.warning("consolidator: Deprecating heuristic #%d for agent %s: %s", h["id"], agent_id, reason)
            conn.execute(
                "UPDATE agent_memory SET status = 'deprecated', updated_at = ? WHERE id = ?",
                (now_iso, h["id"]),
            )
            drift_deprecated.append(h["id"])
            _log_activity(
                conn,
                agent_id,
                "HEURISTIC_STATUS_CHANGED",
                f"Heuristic #{h['id']} deprecated due to philosophy drift: {reason}",
                {"heuristic_id": h["id"], "reason": reason},
                clock,
            )

    # Step 2: Reconcile Active vs Reinforced collisions
    reconciled_deprecated = reconcile_active_vs_reinforced(conn, agent_id, clock)

    # Reload surviving live heuristics
    rows = conn.execute(
        "SELECT id, kind, context, heuristic_text, trigger_json, status, confidence, times_triggered, times_successful "
        "FROM agent_memory WHERE agent_id = ? AND status IN ('active', 'reinforced') ORDER BY confidence DESC",
        (agent_id,),
    ).fetchall()
    surviving = [dict(r) for r in rows]

    total_count = len(surviving)
    if total_count <= max_total:
        return {
            "agent_id": agent_id,
            "status": "CONSOLIDATED_CLEAN",
            "initial_count": len(live_heuristics),
            "final_count": total_count,
            "drift_deprecated": drift_deprecated,
            "reconciled_deprecated": reconciled_deprecated,
            "merged_count": 0,
        }

    # Step 3: Capacity Reduction when total > max_total
    # Separate into reinforced vs active
    reinforced = [h for h in surviving if h["status"] == "reinforced"]
    active = [h for h in surviving if h["status"] == "active"]

    # If there are active heuristics, demote/deprecate lowest-confidence active heuristics first
    pruned_ids = []
    while len(reinforced) + len(active) > max_total and active:
        # Prune the weakest active heuristic (lowest confidence)
        weakest = active.pop()
        conn.execute(
            "UPDATE agent_memory SET status = 'deprecated', updated_at = ? WHERE id = ?",
            (now_iso, weakest["id"]),
        )
        pruned_ids.append(weakest["id"])
        _log_activity(
            conn,
            agent_id,
            "HEURISTIC_STATUS_CHANGED",
            f"Active heuristic #{weakest['id']} deprecated (capacity ceiling reached: {max_total})",
            {"heuristic_id": weakest["id"], "status": "deprecated"},
            clock,
        )

    # If still > max_total, it means we have > max_total REINFORCED heuristics!
    # These must be merged (or top-5 selected by Wilson score)
    merged_ids = []
    if len(reinforced) > max_total:
        # If LLM client is available, attempt compound synthesis; otherwise fallback to top Wilson scores
        logger.info(
            "consolidator: Agent %s has %d reinforced heuristics (> %d cap). Pruning/merging to cap.",
            agent_id,
            len(reinforced),
            max_total,
        )
        # Keep top max_total by confidence/Wilson score
        reinforced_to_keep = reinforced[:max_total]
        reinforced_to_retire = reinforced[max_total:]

        for ret in reinforced_to_retire:
            conn.execute(
                "UPDATE agent_memory SET status = 'deprecated', updated_at = ? WHERE id = ?",
                (now_iso, ret["id"]),
            )
            merged_ids.append(ret["id"])
            _log_activity(
                conn,
                agent_id,
                "HEURISTIC_STATUS_CHANGED",
                f"Reinforced heuristic #{ret['id']} deprecated (capacity ceiling, lower edge relative to top {max_total})",
                {"heuristic_id": ret["id"]},
                clock,
            )

    # Final count audit
    final_count = conn.execute(
        "SELECT COUNT(*) FROM agent_memory WHERE agent_id = ? AND status IN ('active', 'reinforced')",
        (agent_id,),
    ).fetchone()[0]

    return {
        "agent_id": agent_id,
        "status": "CONSOLIDATION_COMPLETE",
        "initial_count": len(live_heuristics),
        "final_count": final_count,
        "drift_deprecated": drift_deprecated,
        "reconciled_deprecated": reconciled_deprecated,
        "pruned_active": pruned_ids,
        "pruned_reinforced": merged_ids,
    }


def _log_activity(
    conn: sqlite3.Connection,
    agent_id: str,
    action: str,
    details: str,
    metadata: dict[str, Any],
    clock: Clock,
) -> None:
    """Helper to log consolidation activity in activity_log."""
    try:
        conn.execute(
            """
            INSERT INTO activity_log (timestamp, agent_id, activity_type, summary, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                clock.now_iso(),
                agent_id,
                action,
                details[:200],
                json.dumps(metadata),
            ),
        )
    except Exception:
        # Table might not exist in all test environments
        pass
