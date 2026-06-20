"""IA-DEVS Simulator for atomic models.

Implements Algorithm 1 from "Uncertainty on Discrete-Event System
Simulation" (VWD21). Wraps a single atomic model and manages the
simulation time bookkeeping (t_last, t_next).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadpya.modeling.interval import Interval

if TYPE_CHECKING:
    from collections.abc import Callable

    from cadpya.engine.protocol import AtomicModel


class Simulator[S, T, X, Y]:
    """IA-DEVS Simulator for a single atomic model (Algorithm 1).

    Type parameters:
        S: base state type
        T: base time type
        X: base input type
        Y: base output type
    """

    __slots__ = ("_model", "_model_factory", "_t_last", "_t_next", "_zero_time")

    def __init__(
        self,
        model_factory: Callable[[Interval[S], Interval[T]], AtomicModel[S, T, X, Y]],
        zero_time: T,
    ) -> None:
        """Create simulator.

        Args:
            model_factory: callable that creates the atomic model
                (typically the model class itself, e.g. Generator).
            zero_time: zero value for the time type (needed for
                elapsed time clamping in the confluent case).
        """
        self._model_factory = model_factory
        self._zero_time = zero_time
        self._model: AtomicModel[S, T, X, Y] | None = None
        self._t_last: Interval[T] | None = None
        self._t_next: Interval[T] | None = None

    def init(self, q_state: Interval[S], q_time: Interval[T], t: Interval[T]) -> None:
        """Initialize simulation (Algorithm 1 init).

        Args:
            q_state: initial sequential state interval
            q_time: initial elapsed time interval (component of total state q)
            t: current simulation time interval

        Sets:
            model = Model(q_state, q_time)
            t_last = t - q_time
            t_next = t_last + TA(state)
        """
        self._model = self._model_factory(q_state, q_time)
        self._t_last = t - q_time
        ta = self._model.time_advance()
        self._t_next = self._t_last + ta if ta is not None else None

    def star_function(self, t: Interval[T]) -> Interval[Y]:
        """Process internal event (Algorithm 1 *-function).

        Args:
            t: current simulation time interval

        Returns:
            Output interval y = Lambda(state)

        Raises:
            RuntimeError: if simulator not initialized
            ValueError: if model is passive or t is not a subset of t_next
        """
        model = self._require_initialized()

        if self._t_next is None:
            msg = "*-function called on passive model (t_next is None)"
            raise ValueError(msg)

        if not t.is_subset_of(self._t_next):
            msg = f"*-function invariant violated: t={t} is not a subset of t_next={self._t_next}"
            raise ValueError(msg)

        # Lambda: compute output BEFORE transition
        y = model.output()

        # Delta_int: update state
        model.internal_transition()

        # Update times
        self._t_last = t
        ta = model.time_advance()
        self._t_next = self._t_last + ta if ta is not None else None

        return y

    def x_function(self, x: Interval[X], t: Interval[T]) -> None:
        """Process external event (Algorithm 1 x-function).

        Args:
            x: input interval
            t: current simulation time interval

        Raises:
            RuntimeError: if simulator not initialized
        """
        model = self._require_initialized()
        assert self._t_last is not None  # guaranteed by init

        # Compute elapsed time interval (t_local)
        t_local = self._compute_elapsed(t)

        # Delta_ext: update state
        model.external_transition(t_local, x)

        # Update times
        self._t_last = t
        ta = model.time_advance()
        self._t_next = self._t_last + ta if ta is not None else None

    @property
    def t_last(self) -> Interval[T]:
        """Time of last processed event."""
        if self._t_last is None:
            msg = "Simulator not initialized"
            raise RuntimeError(msg)
        return self._t_last

    @property
    def t_next(self) -> Interval[T] | None:
        """Time of next scheduled event, or None if passive."""
        return self._t_next

    @property
    def model(self) -> AtomicModel[S, T, X, Y]:
        """Access the underlying atomic model."""
        return self._require_initialized()

    def engine_equals(self, other: object) -> bool:
        """Structural equality for dedup: same t_last, t_next, and model state."""
        if not isinstance(other, Simulator):
            return False
        if self._t_last != other._t_last or self._t_next != other._t_next:
            return False
        if (self._model is None) != (other._model is None):
            return False
        if self._model is None or other._model is None:
            return self._model is None and other._model is None
        return self._model.state_interval == other._model.state_interval

    # -- Internal helpers --------------------------------------------------

    def _require_initialized(self) -> AtomicModel[S, T, X, Y]:
        if self._model is None:
            msg = "Simulator not initialized — call init() first"
            raise RuntimeError(msg)
        return self._model

    def _compute_elapsed(self, t: Interval[T]) -> Interval[T]:
        """Compute elapsed time interval (t_local) per Algorithm 1.

        The elapsed time has asymmetric bounds:
        - Upper: t.upper - t_last.lower (farthest points)
        - Lower: depends on whether t overlaps t_last

        If t intersects t_last (confluent case), the lower bound is
        clamped to 0 — the event could be happening right at the
        last event time.
        """
        assert self._t_last is not None

        # Upper bound: t.upper - t_last.lower
        upper = t.upper - self._t_last.lower  # type: ignore[operator]
        upper_closed = t.upper_closed and self._t_last.lower_closed
        upper_inf = 0
        if t.upper_inf == 1 or self._t_last.lower_inf == -1:
            upper_inf = 1

        # Lower bound
        if t.intersects(self._t_last):
            # Confluent case: event coincides with last event time
            lower = self._zero_time
            lower_closed = True
            lower_inf = 0
        else:
            # Normal case: t.lower - t_last.upper
            lower = t.lower - self._t_last.upper  # type: ignore[operator]
            lower_closed = t.lower_closed and self._t_last.upper_closed
            lower_inf = 0
            if t.lower_inf == 1 or self._t_last.upper_inf == -1:
                lower_inf = 1

        return Interval(
            lower,
            upper,
            lower_closed=lower_closed,
            upper_closed=upper_closed,
            lower_inf=lower_inf,
            upper_inf=upper_inf,
        )
