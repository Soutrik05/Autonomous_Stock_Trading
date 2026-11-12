"""
Registry of PersonaConfig objects: get_persona(id), all_personas(). Adding a persona later means
adding a new config module and one line here, not changing any runner/funnel code.
See Plan_v3 §3.1.
"""

from agents.personas.base import PersonaConfig
from agents.personas.jhunjhunwala import JHUNJHUNWALA
from agents.personas.lynch import LYNCH
from agents.personas.marks import MARKS
from agents.personas.simons import SIMONS
from agents.personas.varsity import VARSITY

_ALL_PERSONAS = [SIMONS, LYNCH, MARKS, JHUNJHUNWALA, VARSITY]

_REGISTRY = {
    SIMONS.id: SIMONS,
    LYNCH.id: LYNCH,
    MARKS.id: MARKS,
    JHUNJHUNWALA.id: JHUNJHUNWALA,
    VARSITY.id: VARSITY,
}

_ALIASES = {
    "stockminds-core": "varsity",
    "stockminds": "varsity",
    "core": "varsity",
    "varsity-dcf": "varsity",
    "baseline-simons-rules": "simons",
    "baseline-varsity-rules": "varsity",
    "baseline-lynch-rules": "lynch",
    "baseline-marks-rules": "marks",
    "baseline-rj-rules": "jhunjhunwala",
}


def get_persona(persona_id: str) -> PersonaConfig:
    norm = persona_id.lower().replace("agent-", "")
    norm = _ALIASES.get(norm, norm)
    try:
        return _REGISTRY[norm]
    except KeyError:
        raise KeyError(f"Unknown persona id: {persona_id!r}") from None


def all_personas() -> list:
    return list(_ALL_PERSONAS)


__all__ = ["PersonaConfig", "get_persona", "all_personas"]
