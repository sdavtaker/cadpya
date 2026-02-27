"""IA-DEVS atomic model protocol.

Defines the structural typing interface that all IA-DEVS atomic models
must satisfy. Models are plain classes — no inheritance required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cadpya.modeling.interval import Interval


@runtime_checkable
class AtomicModel[S, T, X, Y](Protocol):
    """IA-DEVS atomic model interface.

    Models are plain classes satisfying this protocol via structural
    subtyping. No inheritance required.

    Type parameters:
        S: base state type (e.g. Decimal, ProcessorState, CounterState)
        T: base time type (e.g. Decimal)
        X: base input type (e.g. Decimal, int, InputEvent)
        Y: base output type (e.g. Decimal, int)
    """

    def internal_transition(self) -> None: ...
    def external_transition(self, elapsed: Interval[T], x: Interval[X]) -> None: ...
    def output(self) -> Interval[Y]: ...
    def time_advance(self) -> Interval[T] | None: ...

    @property
    def state_interval(self) -> Interval[S]: ...
