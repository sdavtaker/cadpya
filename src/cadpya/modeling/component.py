"""Component specification for coupled models.

A ComponentSpec describes everything needed to instantiate and initialize
one sub-model inside a coupled model. The Coordinator uses these specs
to create engines (Simulator for atomic models, sub-Coordinator for
coupled models).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from cadpya.modeling.coupled import CoupledModel
    from cadpya.modeling.interval import Interval


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    """Specification for one sub-model in a coupled model.

    Either atomic (has model_factory + initial_state + initial_elapsed)
    or coupled (has coupled_model). Use the factory methods ``atomic()``
    and ``coupled()`` for clarity.
    """

    model_factory: Callable[[Interval[Any], Interval[Any]], Any] | None
    initial_state: Interval[Any] | None
    initial_elapsed: Interval[Any] | None
    coupled_model: CoupledModel[Any] | None = None

    @classmethod
    def atomic(
        cls,
        model_factory: Callable[[Interval[Any], Interval[Any]], Any],
        initial_state: Interval[Any],
        initial_elapsed: Interval[Any],
    ) -> ComponentSpec:
        """Create a spec for an atomic model."""
        return cls(
            model_factory=model_factory,
            initial_state=initial_state,
            initial_elapsed=initial_elapsed,
            coupled_model=None,
        )

    @classmethod
    def coupled(cls, coupled_model: CoupledModel[Any]) -> ComponentSpec:
        """Create a spec for a nested coupled model."""
        return cls(
            model_factory=None,
            initial_state=None,
            initial_elapsed=None,
            coupled_model=coupled_model,
        )

    @property
    def is_atomic(self) -> bool:
        """True if this spec describes an atomic model."""
        return self.model_factory is not None

    @property
    def is_coupled(self) -> bool:
        """True if this spec describes a nested coupled model."""
        return self.coupled_model is not None

    def __post_init__(self) -> None:
        has_factory = self.model_factory is not None
        has_state = self.initial_state is not None
        has_elapsed = self.initial_elapsed is not None
        has_coupled = self.coupled_model is not None

        if has_coupled and has_factory:
            msg = (
                "ComponentSpec cannot have both model_factory and coupled_model. "
                "Use ComponentSpec.atomic() or ComponentSpec.coupled()."
            )
            raise ValueError(msg)

        if not has_coupled and not has_factory:
            msg = (
                "ComponentSpec must have either model_factory (atomic) or "
                "coupled_model (coupled). Use ComponentSpec.atomic() or "
                "ComponentSpec.coupled()."
            )
            raise ValueError(msg)

        if has_factory and (not has_state or not has_elapsed):
            msg = (
                "Atomic ComponentSpec requires initial_state and initial_elapsed. "
                "Use ComponentSpec.atomic(factory, state, elapsed)."
            )
            raise ValueError(msg)

        if has_coupled and (has_state or has_elapsed):
            msg = (
                "Coupled ComponentSpec should not have initial_state or "
                "initial_elapsed. Use ComponentSpec.coupled(model)."
            )
            raise ValueError(msg)
