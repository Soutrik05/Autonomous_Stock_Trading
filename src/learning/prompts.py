"""
Prompt text for the weekly reflection LLM call (learning/engine.py). Kept separate from
agents/prompt_base.py since this is a review-the-past prompt, not a decide-tonight prompt, and
has its own output contract (a heuristics list, not a decisions list).
See Plan_v3 §5.4.
"""

from typing import Any

_ALLOWED_OPERATORS = ">, >=, <, <=, ==, !="

# One line per learning/forensics.py SECONDARY_TAGS entry. Kept here (not in forensics.py)
# since it's prompt-facing wording, not classification logic.
_SECONDARY_TAG_MEANINGS = {
    "WEAK_MARKET": "the broader market/VIX was elevated for most of the hold",
    "LATE_ENTRY": "price had already run up sharply right before entry",
    "GAP_DOWN": "a sharp overnight gap-down occurred during the hold",
    "DEEP_DRAWDOWN_THEN_RECOVERED": "the trade was deeply underwater at some point but the exit result recovered well above that low",
    "GAVE_BACK_PROFIT": "the trade was up a lot at its best point but gave most of that back by exit",
    "EXITED_TOO_EARLY": "the stock kept running well after this agent exited",
    "GOOD_EXIT": "the stock kept falling after this agent exited -- the exit timing was good",
    "STOP_TOO_TIGHT": "this was a stop-loss exit, but price recovered back above entry within days",
}

OUTPUT_CONTRACT = """OUTPUT CONTRACT
Return ONLY one JSON object, no commentary, no code fences:
{{
  "heuristics": [
    {{
      "context": "ENTRY",
      "kind": "SEEK",
      "heuristic_text": "one short sentence, at most 200 characters",
      "trigger": {{"feature": "rsi_14", "op": ">", "value": 55}},
      "prescribed_action": "what the agent should do when this fires",
      "rationale": "one or two sentences citing the specific closed trades that support this"
    }}
  ]
}}
- context is either "ENTRY" (default, evaluating candidate buy decisions) or "EXIT" (evaluating open positions nightly).
  * ENTRY context:
    - kind "SEEK": look for high-probability setups to BUY.
    - kind "AVOID": do NOT buy when this trigger condition is present (e.g. overextended run-up, high VIX, false breakout).
  * EXIT context (for managing open positions):
    - kind "SEEK": exit/sell signal when an open position meets this trigger. Use this to address trades tagged GAVE_BACK_PROFIT (e.g., sell to lock in profit when momentum stalls or indicator rolls over).
    - kind "AVOID": hold signal (do NOT sell yet) while this trigger holds. Use this to address trades tagged EXITED_TOO_EARLY (e.g., stay in trend as long as ADX/EMA support holds).
- kind is exactly "SEEK" or "AVOID".
- heuristic_text is a single short sentence, at most 200 characters.
- trigger is a predicate using ONLY these metric names: {allowed_metrics}
  Use ONLY these operators: {allowed_operators}
  A trigger may combine conditions with {{"all": [...]}} or {{"any": [...]}} of the same leaf form.
  The numbers and tags shown for each trade below (mae_pct, mfe_pct, secondary tags, etc.) are
  for YOUR understanding of what happened -- they are NOT valid trigger feature names. A trigger
  must be built only from the allowed metric names above.
- Propose AT MOST {max_heuristics} heuristics. Prefer fewer, stronger rules over many weak ones.
- A loss classified CORP_ACTION_ARTIFACT or BROAD_MARKET_DRAG is bad luck or market-wide noise,
  not a pattern in this agent's own decisions -- it must NEVER produce an AVOID heuristic.
- A trade tagged GAVE_BACK_PROFIT entered fine and lost on the exit, not the entry -- it is an
  exit problem, not an entry problem. Do NOT propose an entry AVOID heuristic from such trades
  alone; propose an EXIT-context SEEK heuristic instead.
- A trade tagged EXITED_TOO_EARLY cut winners prematurely -- propose an EXIT-context AVOID heuristic
  (hold signal) to let trends run.
- An empty "heuristics" list is valid and normal when the evidence does not support a new rule.
- Every heuristic must be testable purely from the metric names above -- nothing you cannot see
  in the data given.
- Structure heuristics with robust, philosophy-aligned predicates: For fundamental/swing personas (Lynch, Marks, Jhunjhunwala), prefer compound conditions with {{"all": [...]}} that combine business quality/valuation (ROCE, PEG, D/E, PAT growth) with technical/regime validation rather than isolated single-indicator thresholds.
- Propose rules that fit this investor's philosophy, described below. Do not turn this agent
  into a different kind of investor."""


def _full_description(system_prompt: str) -> str:
    """The persona's full philosophy paragraph: everything in its system_prompt before the
    'HOLDING HORIZON:' section (present in every persona's prompt -- see
    agents/personas/*.py and agents/prompt_base.py). PersonaConfig has no dedicated long
    description field, and docs/personas.md is pure documentation never read by
    agents/personas.py at runtime, so this is the richest description actually sourced from
    the code path personas use."""
    description = system_prompt.split("HOLDING HORIZON:")[0].strip()
    return description or "Disciplined systematic trader."


def _format_number(value) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def _format_trade(trade: dict) -> str:
    parts = [
        f"{trade['ticker']}: entered {trade['entry_date']}, exited {trade['exit_date']} "
        f"({trade['hold_days']}d hold), realized_pnl_pct={trade['realized_pnl_pct']:.2f}%, "
        f"exit_reason={trade['exit_reason']}, forensics_type={trade['forensics_type']}",
        (
            "  numbers: mae="
            + _format_number(trade.get("mae_pct"))
            + ", mfe="
            + _format_number(trade.get("mfe_pct"))
            + ", profit_given_back="
            + _format_number(trade.get("profit_given_back_pct"))
            + ", run_up_before_entry="
            + _format_number(trade.get("run_up_before_entry_pct"))
            + ", largest_gap_down="
            + _format_number(trade.get("largest_gap_down_pct"))
        ),
    ]
    post_exit = trade.get("post_exit")
    if post_exit:
        post_exit_text = ", ".join(f"{k}={v}" for k, v in post_exit.items())
        parts.append(f"  post-exit: {post_exit_text}")
    if trade.get("secondary_tags"):
        parts.append(f"  secondary tags: {', '.join(trade['secondary_tags'])}")
    if trade.get("diagnosis_reason"):
        parts.append(f"  diagnosis: {trade['diagnosis_reason']}")
    if trade.get("entry_features"):
        features_text = ", ".join(f"{k}={v}" for k, v in trade["entry_features"].items())
        parts.append(f"  entry features: {features_text}")
    return "\n".join(parts)


def _format_existing_heuristics(existing_heuristics: list[dict]) -> str:
    if not existing_heuristics:
        return "none yet."
    lines = [f"- [{h['kind']}/{h['status']}] {h['heuristic_text']}" for h in existing_heuristics]
    return "\n".join(lines)


def _format_secondary_tag_legend(secondary_tags: list[str]) -> str:
    lines = [f"- {tag}: {_SECONDARY_TAG_MEANINGS.get(tag, '(see learning/forensics.py)')}" for tag in secondary_tags]
    return "\n".join(lines)


def build_reflection_system_prompt(
    persona_name: str,
    persona_system_prompt: str,
    allowed_metrics: list[str],
    loss_labels: list[str],
    win_labels: list[str],
    secondary_tags: list[str],
    max_heuristics: int,
) -> str:
    allowed_metrics_text = ", ".join(allowed_metrics)
    description = _full_description(persona_system_prompt)
    return f"""You are a disciplined post-mortem analyst reviewing {persona_name}'s paper-trading account.

{persona_name}'s investing philosophy, in full:
{description}

Your only job this review is to read what already happened to CLOSED trades and propose new,
testable heuristics from the empirical evidence. You are not re-deciding any trade, and you must not
invent facts not present in the trade data given to you.

Deliberation & Reflection Methodology (conduct in your internal reasoning):
1. ANCHOR ON BASE RATES: Inspect aggregate base rates, MAE/MFE profile, and loss class distribution.
   Distinguish systematic patterns from isolated market-wide drag or corporate actions.
2. DIAGNOSE LEAKAGE CONTEXT:
   - If losses stem from poor entry timing or extended run-ups (e.g. LATE_ENTRY, FALSE_BREAKOUT), formulate an ENTRY AVOID rule.
   - If trades captured open profit but collapsed before exit (GAVE_BACK_PROFIT), formulate an EXIT SEEK rule (sell signal to lock gains).
   - If winners were cut prematurely and continued running (EXITED_TOO_EARLY), formulate an EXIT AVOID rule (hold signal to let winners run).
3. FORMULATE EXACT PREDICATE: Build machine-checkable triggers using ONLY the allowed metric names and operators.
   Verify that proposed thresholds cleanly separate historical winners from losers.
4. CLEAN OUTPUT CONTRACT: Emit ONLY the final {{"heuristics": [...]}} JSON object with concise heuristic_text and rationale.
   All conversational deliberation must remain strictly within thinking/reasoning tokens.

The post-mortem classifier can label a closed trade with exactly one of these loss classes:
{", ".join(loss_labels)}
or, for a win, exactly one of these win classes:
{", ".join(win_labels)}

Each trade may also carry one or more of these independent secondary tags (context only, never
usable as a trigger feature name):
{_format_secondary_tag_legend(secondary_tags)}

{OUTPUT_CONTRACT.format(allowed_metrics=allowed_metrics_text, allowed_operators=_ALLOWED_OPERATORS, max_heuristics=max_heuristics)}
"""


def _format_forensics_summary(summary: dict[str, Any] | None) -> str:
    if not summary or summary.get("total_closed", 0) == 0:
        return "none available yet."

    total = summary["total_closed"]
    wins = summary.get("win_trades", 0)
    losses = summary.get("loss_trades", 0)

    avg_mae = summary.get("avg_mae_pct")
    avg_mfe = summary.get("avg_mfe_pct")
    avg_pgb = summary.get("avg_give_back_pct")

    mae_str = f"{avg_mae:.2f}%" if avg_mae is not None else "n/a"
    mfe_str = f"{avg_mfe:.2f}%" if avg_mfe is not None else "n/a"
    pgb_str = f"{avg_pgb:.2f}%" if avg_pgb is not None else "n/a"

    lines = [
        f"- Sample Base Rate: {total} total closed trades ({wins} wins, {losses} losses)",
        f"- Excursions Profile: avg MAE={mae_str}, avg MFE={mfe_str}, avg Profit Given Back={pgb_str}",
    ]

    loss_classes = summary.get("loss_classes", {})
    if loss_classes:
        lc_strs = [
            f"{cls}: {count} ({count / losses * 100:.1f}%)" if losses else f"{cls}: {count}"
            for cls, count in sorted(loss_classes.items(), key=lambda x: -x[1])
        ]
        lines.append(f"- Loss Classes: {', '.join(lc_strs)}")

    tags = summary.get("secondary_tags", {})
    if tags:
        tag_strs = [f"{tag}: {count}" for tag, count in sorted(tags.items(), key=lambda x: -x[1])]
        lines.append(f"- Secondary Tags Frequency: {', '.join(tag_strs)}")

    fb = summary.get("fb_split", {})
    if fb.get("total", 0) > 0:
        lines.append(
            f"- FALSE_BREAKOUT Diagnostics: {fb['total']} total "
            f"({fb['no_follow']} no-follow [{fb.get('no_follow_pct', 0.0):.1f}%], "
            f"{fb['give_back']} gave-back [{fb.get('give_back_pct', 0.0):.1f}%])"
        )

    return "\n".join(lines)


def build_reflection_user_prompt(
    eligible_trades: list[dict],
    existing_heuristics: list[dict],
    forensics_summary: dict[str, Any] | None = None,
) -> str:
    trades_text = "\n".join(_format_trade(t) for t in eligible_trades)
    summary_text = _format_forensics_summary(forensics_summary)
    return f"""EXISTING HEURISTICS (do not repeat these):
{_format_existing_heuristics(existing_heuristics)}

AGGREGATE FORENSICS & BASE RATES:
{summary_text}

CLOSED TRADES SINCE LAST REVIEW:
{trades_text}
"""


def build_reflection_repair_prompt(original_user_prompt: str, validation_error: str) -> str:
    return (
        f"{original_user_prompt}\n\n"
        "Your previous response was not valid JSON matching the required format. Error:\n"
        f"{validation_error}\n\n"
        "Return ONLY corrected JSON matching the exact schema, with no extra commentary and no code fences."
    )
