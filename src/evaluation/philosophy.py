"""
Persona Philosophy Adherence Evaluator.
Scores how faithfully each agent adheres to its foundational investment tenets across
three orthogonal dimensions:
  1. Entry Selection Fidelity: Adherence to quantitative hurdles (technical & fundamental).
  2. Holding Horizon Fidelity: Congruence between trade holding duration/exit reasons and strategy type.
  3. Cognitive Citation Fidelity: Validity of cited metrics against the persona's allowed domain.

Directly references PersonaConfig and contracts as the single source of truth.
"""

import json
import sqlite3
from typing import Any

from agents.personas import get_persona
from agents.personas.base import PersonaConfig
from features.contracts import evaluate_predicate, persona_allowed_metric_names


def resolve_persona_id(agent_id: str) -> str:
    """
    Normalizes an agent_id or baseline_id to the base persona identifier.
    E.g., 'baseline-lynch-rules' -> 'lynch', 'baseline-rj-rules' -> 'jhunjhunwala'.
    """
    norm = agent_id.lower().replace("agent-", "")
    if norm.startswith("baseline-"):
        base = norm.replace("baseline-", "").replace("-rules", "")
        if base == "rj":
            return "jhunjhunwala"
        return base
    if norm in ("rj", "jhunjhunwala"):
        return "jhunjhunwala"
    if norm in ("stockminds-core", "stockminds", "core", "varsity-dcf"):
        return "varsity"
    return norm


def resolve_persona(agent_id: str) -> PersonaConfig | None:
    """Loads the PersonaConfig for the given agent or returns None if unrecognized."""
    base_id = resolve_persona_id(agent_id)
    try:
        return get_persona(base_id)
    except Exception:
        return None


def _extract_leaf_predicates(pred: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Flattens a boolean predicate tree into named leaf rules."""
    leaves: list[tuple[str, dict[str, Any]]] = []
    if not pred:
        return leaves
    if "all" in pred and isinstance(pred["all"], list):
        for child in pred["all"]:
            leaves.extend(_extract_leaf_predicates(child))
    elif "any" in pred and isinstance(pred["any"], list):
        for child in pred["any"]:
            leaves.extend(_extract_leaf_predicates(child))
    elif "feature" in pred:
        label = f"{pred.get('feature')} {pred.get('op')} {pred.get('value')}"
        leaves.append((label, pred))
    return leaves


def evaluate_decision_philosophy(
    agent_id: str,
    decision_row: dict[str, Any],
    features: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluates one BUY decision against its persona's hurdles.
    Returns: {tenets_checked: int, tenets_passed: int, passed: bool, details: dict}
    """
    persona = resolve_persona(agent_id)
    if not persona:
        return {"tenets_checked": 0, "tenets_passed": 0, "passed": True, "details": {}}

    tech_hurdles = persona.technical_hurdles or {}
    fund_hurdles = persona.fundamental_hurdles or {}

    tech_leaves = _extract_leaf_predicates(tech_hurdles)
    fund_leaves = _extract_leaf_predicates(fund_hurdles)
    all_leaves = tech_leaves + fund_leaves

    details: dict[str, bool] = {}
    passed_count = 0

    for label, leaf in all_leaves:
        res = evaluate_predicate(features, leaf)
        details[label] = res
        if res:
            passed_count += 1

    # Overall selection compliance requires satisfying the full compound predicates
    tech_ok = evaluate_predicate(features, tech_hurdles) if tech_hurdles else True
    fund_ok = evaluate_predicate(features, fund_hurdles) if fund_hurdles else True

    # If persona has risk-reward requirement (e.g. Simons target/stop discipline)
    simons_risk_ok = True
    if persona.strategy_type == "QUANT_MOMENTUM":
        t_paise = decision_row.get("target_paise")
        s_paise = decision_row.get("stop_paise")
        e_paise = decision_row.get("entry_high_paise")
        if t_paise and s_paise and e_paise and (e_paise > s_paise):
            risk = e_paise - s_paise
            reward = t_paise - e_paise
            simons_risk_ok = reward >= 1.0 * risk
            details["rrr_ge_1_0"] = simons_risk_ok
            if simons_risk_ok:
                passed_count += 1
            all_leaves.append(("rrr_ge_1_0", {}))

    is_compliant = tech_ok and fund_ok and simons_risk_ok
    total = len(all_leaves)

    return {
        "tenets_checked": total,
        "tenets_passed": passed_count,
        "passed": is_compliant,
        "details": details,
        "technical_passed": tech_ok,
        "fundamental_passed": fund_ok,
    }


def evaluate_selection_fidelity(
    agent_id: str,
    dec_rows: list[sqlite3.Row | dict[str, Any]],
) -> dict[str, Any]:
    """
    Dimension 1: Scores adherence of BUY decisions to quantitative entry hurdles.
    """
    total_buys = len(dec_rows)
    if total_buys == 0:
        return {
            "score": 100.0,
            "total_buys": 0,
            "compliant_buys": 0,
            "tenet_stats": {},
        }

    compliant_buys = 0
    tenet_passes: dict[str, int] = {}
    tenet_totals: dict[str, int] = {}

    for r in dec_rows:
        dec_data = {
            "entry_high_paise": r["entry_high_paise"],
            "stop_paise": r["stop_paise"],
            "target_paise": r["target_paise"],
        }
        features: dict[str, Any] = {}
        if r["features_json"]:
            try:
                features = json.loads(r["features_json"])
            except Exception:
                pass

        res = evaluate_decision_philosophy(agent_id, dec_data, features)
        if res["passed"]:
            compliant_buys += 1

        for tname, tstatus in res["details"].items():
            tenet_totals[tname] = tenet_totals.get(tname, 0) + 1
            if tstatus:
                tenet_passes[tname] = tenet_passes.get(tname, 0) + 1

    score = round((compliant_buys / total_buys) * 100.0, 1)
    tenet_stats = {
        k: {
            "passed": tenet_passes.get(k, 0),
            "total": tenet_totals.get(k, 0),
            "pct": round((tenet_passes.get(k, 0) / max(1, tenet_totals.get(k, 1))) * 100.0, 1),
        }
        for k in tenet_totals
    }

    return {
        "score": score,
        "total_buys": total_buys,
        "compliant_buys": compliant_buys,
        "tenet_stats": tenet_stats,
    }


def evaluate_horizon_fidelity(
    agent_id: str,
    pos_rows: list[sqlite3.Row | dict[str, Any]],
) -> dict[str, Any]:
    """
    Dimension 2: Evaluates holding duration and exit rationale congruence with strategy type.
    """
    persona = resolve_persona(agent_id)
    total_closed = len(pos_rows)
    if not persona or total_closed == 0:
        return {
            "score": 100.0,
            "total_closed": total_closed,
            "compliant_closed": float(total_closed),
        }

    stype = persona.strategy_type
    compliance_units = 0.0

    for r in pos_rows:
        h = r["hold_days"] or 0
        ex = r["exit_reason"] or ""
        ft = r["forensics_type"] or ""
        pnl = r["realized_pnl_pct"] or 0.0

        if stype == "QUANT_MOMENTUM":
            if h <= 20:
                compliance_units += 1.0
            elif h <= 30:
                compliance_units += 0.5
            else:
                compliance_units += 0.1
        elif stype == "HYBRID":
            if 7 <= h <= 50:
                compliance_units += 1.0
            elif h > 50:
                compliance_units += 0.5
            else:
                compliance_units += 0.8 if ex in ("STOP_HIT", "TRAILING_STOP_HIT") else 0.2
        elif stype in ("GARP", "VALUE_CONTRARIAN"):
            if h >= 30:
                compliance_units += 1.0
            elif ft in ("EARNINGS_SHOCK", "BROAD_MARKET_DRAG") or pnl <= -10.0 or ex in ("STOP_HIT", "TRAILING_STOP_HIT"):
                compliance_units += 0.8  # Legitimate stop / fundamental invalidation
            else:
                compliance_units += 0.2  # Premature technical shakeout
        elif stype == "GROWTH_COMPOUNDER":
            if h >= 45:
                compliance_units += 1.0
            elif ft in ("EARNINGS_SHOCK", "BROAD_MARKET_DRAG") or pnl <= -12.0 or ex in ("STOP_HIT", "TRAILING_STOP_HIT"):
                compliance_units += 0.8  # Legitimate structural breakdown
            else:
                compliance_units += 0.2  # Premature exit
        else:
            compliance_units += 1.0

    score = round((compliance_units / total_closed) * 100.0, 1)
    return {
        "score": score,
        "total_closed": total_closed,
        "compliant_closed": compliance_units,
    }


def evaluate_citation_fidelity(
    agent_id: str,
    dec_rows: list[sqlite3.Row | dict[str, Any]],
) -> dict[str, Any]:
    """
    Dimension 3: Evaluates whether the metrics cited in decision rationales fall within
    the persona's authorized analytical domain.
    """
    persona = resolve_persona(agent_id)
    if not persona:
        return {"score": 100.0, "total_cited": 0, "valid_cited": 0}

    allowed = set(
        persona_allowed_metric_names(
            persona.technical_hurdles,
            persona.fundamental_hurdles,
            extra_metrics=list(persona.extra_metrics),
        )
    )

    total_cited = 0
    valid_cited = 0

    for r in dec_rows:
        raw = r["cited_metrics_json"]
        if not raw:
            continue
        try:
            metrics_data = json.loads(raw)
            if isinstance(metrics_data, dict):
                metric_keys = list(metrics_data.keys())
            elif isinstance(metrics_data, list):
                metric_keys = metrics_data
            else:
                metric_keys = []

            for m in metric_keys:
                total_cited += 1
                if m in allowed:
                    valid_cited += 1
        except Exception:
            pass

    score = round((valid_cited / total_cited) * 100.0, 1) if total_cited > 0 else 100.0
    return {
        "score": score,
        "total_cited": total_cited,
        "valid_cited": valid_cited,
    }


def evaluate_agent_philosophy_adherence(conn: sqlite3.Connection, agent_id: str) -> dict[str, Any]:
    """
    Calculates overall philosophy adherence across Entry Selection, Holding Horizon,
    and Cognitive Citation dimensions.
    """
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "decisions" not in tables or "feature_snapshots" not in tables:
        return {
            "agent_id": agent_id,
            "total_buys": 0,
            "compliant_buys": 0,
            "adherence_pct": 100.0,
            "composite_score": 100.0,
            "selection_fidelity": 100.0,
            "horizon_fidelity": 100.0,
            "citation_fidelity": 100.0,
            "status": "FAITHFUL",
            "tenet_stats": {},
        }

    # 1. Fetch BUY decisions
    dec_rows = conn.execute(
        """
        SELECT d.id, d.ticker, d.shares, d.entry_high_paise, d.stop_paise, d.target_paise,
               d.cited_metrics_json, fs.features_json
        FROM decisions d
        JOIN feature_snapshots fs ON d.snapshot_id = fs.id
        WHERE d.agent_id = ? AND d.action = 'BUY'
        """,
        (agent_id,),
    ).fetchall()

    # 2. Fetch Closed positions if table exists
    pos_rows: list[sqlite3.Row] = []
    if "positions" in tables:
        pos_rows = conn.execute(
            """
            SELECT hold_days, exit_reason, forensics_type, realized_pnl_pct
            FROM positions
            WHERE agent_id = ? AND status = 'CLOSED'
            """,
            (agent_id,),
        ).fetchall()

    # Evaluate 3 dimensions
    sel_eval = evaluate_selection_fidelity(agent_id, dec_rows)
    hor_eval = evaluate_horizon_fidelity(agent_id, pos_rows)
    cit_eval = evaluate_citation_fidelity(agent_id, dec_rows)

    s_score = sel_eval["score"]
    h_score = hor_eval["score"]
    c_score = cit_eval["score"]

    # Composite weighting:
    # If positions have closed, weight 40% Selection, 40% Horizon, 20% Citation
    # If no closed positions yet, weight 70% Selection, 30% Citation
    if hor_eval["total_closed"] > 0:
        composite = round(0.40 * s_score + 0.40 * h_score + 0.20 * c_score, 1)
    elif sel_eval["total_buys"] > 0:
        composite = round(0.70 * s_score + 0.30 * c_score, 1)
    else:
        composite = 100.0

    if composite >= 80.0:
        status = "FAITHFUL"
    elif composite >= 65.0:
        status = "MODERATE_DRIFT"
    else:
        status = "STYLE_DRIFT"

    persona = resolve_persona(agent_id)
    strategy_type = persona.strategy_type if persona else "UNKNOWN"

    return {
        "agent_id": agent_id,
        "strategy_type": strategy_type,
        "total_buys": sel_eval["total_buys"],
        "compliant_buys": sel_eval["compliant_buys"],
        "adherence_pct": composite,  # Preserves backwards compatibility
        "composite_score": composite,
        "selection_fidelity": s_score,
        "horizon_fidelity": h_score,
        "citation_fidelity": c_score,
        "status": status,
        "tenet_stats": sel_eval["tenet_stats"],
        "total_closed_positions": hor_eval["total_closed"],
    }
