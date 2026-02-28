"""IA-DEVS coupled model definition.

A CoupledModel is a pure data structure describing the static coupling
topology: components, influencers, translation functions, and SELECT.
It has no simulation behavior — the Coordinator consumes this.

Corresponds to the formal tuple C = <X, Y, D, M, I, Z, SELECT>.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from cadpya.modeling.component import ComponentSpec
    from cadpya.modeling.interval import Interval


@dataclass(frozen=True, slots=True)
class CoupledModel[T]:
    """IA-DEVS coupled model definition.

    Type parameters:
        T: base time type (shared across all components)

    Fields:
        components: name → ComponentSpec mapping (D + M from the formalism)
        influencers: name → set of influencing component names (I from the formalism).
            Every component must have an entry (empty frozenset is valid).
            The key ``"self"`` describes external output couplings (EOC).
        translations: (source, dest) → Z translation function.
            Three coupling types: IC, EOC (dest="self"), EIC (source="self").
        select: tie-breaking function SELECT: frozenset[str] → str.
        zero_time: shared zero value for the time type.
    """

    components: dict[str, ComponentSpec]
    influencers: dict[str, frozenset[str]]
    translations: dict[tuple[str, str], Callable[[Interval[Any]], Interval[Any]]]
    select: Callable[[frozenset[str]], str]
    zero_time: T

    def __post_init__(self) -> None:
        _validate(self)


def _format_names(names: frozenset[str] | set[str]) -> str:
    """Format a set of names for error messages."""
    if not names:
        return "[none]"
    return "[" + ", ".join(f"'{n}'" for n in sorted(names)) + "]"


def _validate(model: CoupledModel[Any]) -> None:
    component_names = frozenset(model.components.keys())

    # Rule 1: at least one component
    if not component_names:
        msg = "Validation error: coupled model must have at least one component"
        raise ValueError(msg)

    # Rule 7: "self" is reserved
    if "self" in component_names:
        msg = "Validation error: 'self' is a reserved name and cannot be used as a component name"
        raise ValueError(msg)

    valid_names = component_names | {"self"}

    # Rule 2: all influencer references exist
    for dest, sources in model.influencers.items():
        if dest not in valid_names:
            msg = (
                f"Validation error: '{dest}' is an influencer destination "
                f"but does not exist. "
                f"Available components: {_format_names(component_names)}"
            )
            raise ValueError(msg)
        for source in sources:
            if source not in valid_names:
                msg = (
                    f"Validation error: '{source}' is listed as an influencer "
                    f"of '{dest}' but does not exist. "
                    f"Available components: {_format_names(component_names)}"
                )
                raise ValueError(msg)

    # Rule 3: all components have influencer entries
    for name in component_names:
        if name not in model.influencers:
            msg = (
                f"Validation error: component '{name}' has no influencer entry "
                f"(empty set is valid but must be explicitly registered)"
            )
            raise ValueError(msg)

    # Rule 4: all translation endpoints exist
    for source, dest in model.translations:
        if source not in valid_names:
            msg = (
                f"Validation error: translation source '{source}' does not exist. "
                f"Available components: {_format_names(component_names)}"
            )
            raise ValueError(msg)
        if dest not in valid_names:
            msg = (
                f"Validation error: translation destination '{dest}' does not exist. "
                f"Available components: {_format_names(component_names)}"
            )
            raise ValueError(msg)

    # Rule 5: translations match influencers
    for source, dest in model.translations:
        if dest != "self" and source != "self":
            inf_set = model.influencers.get(dest, frozenset())
            if source not in inf_set:
                msg = (
                    f"Validation error: translation from '{source}' to '{dest}' "
                    f"exists, but '{source}' is not listed as an influencer of "
                    f"'{dest}'"
                )
                raise ValueError(msg)

    # Rule 6: influencers have translations
    for dest, sources in model.influencers.items():
        for source in sources:
            if (source, dest) not in model.translations:
                msg = (
                    f"Validation error: '{source}' is listed as an influencer "
                    f"of '{dest}', but no translation function "
                    f"('{source}', '{dest}') is registered"
                )
                raise ValueError(msg)
