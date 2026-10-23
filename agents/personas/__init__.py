"""
Registry of PersonaConfig objects: get_persona(id), all_personas(). Adding a persona later means
adding a new config module and one line here, not changing any runner/funnel code.
See Plan_v3 §3.1.
"""
from agents.personas.base import PersonaConfig
from agents.personas.simons import SIMONS

_REGISTRY = {
    SIMONS.id: SIMONS,
}


def get_persona(persona_id: str) -> PersonaConfig:
    try:
        return _REGISTRY[persona_id]
    except KeyError:
        raise KeyError(f"Unknown persona id: {persona_id!r}") from None


def all_personas() -> list:
    return list(_REGISTRY.values())


__all__ = ["PersonaConfig", "get_persona", "all_personas"]
