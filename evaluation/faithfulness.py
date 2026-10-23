"""
Compares each decision's cited_metrics against its saved FeatureSnapshot using per-feature match rules.
See Plan_v3 §3.3.
"""
from typing import Any, Dict

from core.features import matches


def compute_faithfulness(cited_metrics: Dict[str, Any], features: Dict[str, Any]) -> float:
    """faithfulness_score = matched / max(len(cited_metrics), 3): citing fewer than 3 metrics is
    penalised by the denominator, not exempted from it. A name outside the FeatureSnapshot
    registry, or a value matches() rejects, counts as a mismatch (matches() already returns
    False for both cases)."""
    if not cited_metrics:
        return 0.0
    context = {"close": features.get("close")}
    matched = sum(
        1
        for name, cited_value in cited_metrics.items()
        if matches(name, cited_value, features.get(name), context)
    )
    return matched / max(len(cited_metrics), 3)
