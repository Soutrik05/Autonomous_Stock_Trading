"""
Telemetry and audit utilities for tracking agent heuristic compliance.
Analyzes whether underperformance stems from bad heuristics vs. agent defiance.
"""

import json
import logging
import sqlite3
from typing import Any

from core.clock import Clock
from core.config import settings

logger = logging.getLogger(__name__)


def compute_compliance_summary(
    conn: sqlite3.Connection,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Computes per-heuristic compliance rates and performance correlation.
    Returns structured metrics classifying each heuristic into actionable diagnostic states.
    """
    query = """
        SELECT
            am.id AS heuristic_id,
            am.agent_id,
            am.kind,
            COALESCE(am.context, 'ENTRY') AS context,
            am.heuristic_text,
            am.status,
            am.confidence,
            COUNT(ha.id) AS total_fires,
            SUM(CASE WHEN ha.complied IS NOT NULL THEN 1 ELSE 0 END) AS tracked_fires,
            SUM(CASE WHEN ha.complied = 1 THEN 1 ELSE 0 END) AS complied_count,
            SUM(CASE WHEN ha.outcome IN ('SUCCESS', 'FAILURE') THEN 1 ELSE 0 END) AS resolved_count,
            SUM(CASE WHEN ha.outcome = 'SUCCESS' THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN ha.outcome = 'FAILURE' THEN 1 ELSE 0 END) AS failure_count
        FROM agent_memory am
        LEFT JOIN heuristic_applications ha ON ha.heuristic_id = am.id
    """
    params = []
    if agent_id:
        query += " WHERE am.agent_id = ?"
        params.append(agent_id)
    query += " GROUP BY am.id ORDER BY am.agent_id, am.id"

    rows = conn.execute(query, params).fetchall()
    results: list[dict[str, Any]] = []

    for r in rows:
        tracked_fires = r["tracked_fires"] or 0
        complied_count = r["complied_count"] or 0
        resolved_count = r["resolved_count"] or 0
        success_count = r["success_count"] or 0

        compliance_rate = (complied_count / tracked_fires) if tracked_fires > 0 else 0.0
        success_rate = (success_count / resolved_count) if resolved_count > 0 else 0.0

        # Classification
        if tracked_fires < settings.HEURISTIC_COMPLIANCE_MIN_APPLICATIONS:
            classification = "INSUFFICIENT_SAMPLE"
            recommendation = "Gather more empirical observations."
        elif compliance_rate >= 0.70 and success_rate >= 0.50:
            classification = "COMPLIANT_PERFORMING"
            recommendation = "Heuristic is followed and profitable; retain or promote."
        elif compliance_rate >= 0.70 and success_rate < settings.HEURISTIC_ROLLING_DEMOTE_BELOW:
            classification = "COMPLIANT_UNDERPERFORMING"
            recommendation = "Heuristic is followed but failing; candidate for rapid demotion/deprecation."
        elif (
            compliance_rate < settings.HEURISTIC_LOW_COMPLIANCE_THRESHOLD
            and success_rate >= settings.HEURISTIC_HIGH_CONFIDENCE_THRESHOLD
        ):
            classification = "DEFIED_VALID"
            recommendation = "High-confidence valid rule ignored by LLM; reword prompt or escalate to Python check."
        elif (
            compliance_rate < settings.HEURISTIC_LOW_COMPLIANCE_THRESHOLD
            and success_rate < settings.HEURISTIC_ROLLING_DEMOTE_BELOW
        ):
            classification = "DEFIED_INVALID"
            recommendation = "Ignored by LLM and underperforms anyway; deprecate."
        else:
            classification = "NEUTRAL"
            recommendation = "Performance within normal bounds; continue standard lifecycle."

        results.append(
            {
                "heuristic_id": r["heuristic_id"],
                "agent_id": r["agent_id"],
                "kind": r["kind"],
                "context": r["context"],
                "heuristic_text": r["heuristic_text"],
                "status": r["status"],
                "confidence": round(r["confidence"], 3),
                "total_fires": r["total_fires"] or 0,
                "tracked_fires": tracked_fires,
                "complied_count": complied_count,
                "compliance_rate": round(compliance_rate, 4),
                "resolved_count": resolved_count,
                "success_count": success_count,
                "success_rate": round(success_rate, 4),
                "classification": classification,
                "recommendation": recommendation,
            }
        )

    return results


def audit_compliance_and_escalate(conn: sqlite3.Connection, clock: Clock) -> list[dict[str, Any]]:
    """
    Audits active and reinforced heuristics. Escalates heuristics flagged as DEFIED_VALID
    by logging HEURISTIC_COMPLIANCE_BREACH events to activity_log.
    """
    summaries = compute_compliance_summary(conn)
    escalations: list[dict[str, Any]] = []

    for item in summaries:
        if item["status"] not in ("active", "reinforced"):
            continue
        if item["classification"] != "DEFIED_VALID":
            continue

        h_id = item["heuristic_id"]
        agent_id = item["agent_id"]
        comp_pct = item["compliance_rate"] * 100.0
        win_pct = item["success_rate"] * 100.0

        description = (
            f"HEURISTIC_COMPLIANCE_BREACH: Agent {agent_id} defied valid rule #{h_id} "
            f"([{item['context']} {item['kind']}]: {item['heuristic_text'][:60]}) "
            f"compliance={comp_pct:.1f}% (fired {item['tracked_fires']}x), "
            f"win_rate={win_pct:.1f}%"
        )
        metadata = {
            "heuristic_id": h_id,
            "agent_id": agent_id,
            "context": item["context"],
            "kind": item["kind"],
            "compliance_rate": item["compliance_rate"],
            "success_rate": item["success_rate"],
            "tracked_fires": item["tracked_fires"],
            "classification": item["classification"],
            "recommendation": item["recommendation"],
        }

        # Avoid redundant logging on the same day if already recorded
        today_iso = clock.today().isoformat()
        already_logged = conn.execute(
            """
            SELECT 1 FROM activity_log
            WHERE agent_id = ? AND event_type = 'HEURISTIC_COMPLIANCE_BREACH'
              AND metadata_json LIKE ? AND created_at >= ?
            LIMIT 1
            """,
            (agent_id, f'%"heuristic_id": {h_id}%', today_iso),
        ).fetchone()

        if not already_logged:
            conn.execute(
                """
                INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at)
                VALUES (?, 'HEURISTIC_COMPLIANCE_BREACH', NULL, ?, ?, ?)
                """,
                (agent_id, description, json.dumps(metadata), clock.now_iso()),
            )
            logger.warning("Compliance audit: %s", description)

        escalations.append(metadata)

    return escalations
