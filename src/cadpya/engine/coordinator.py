"""IA-DEVS Coordinator for coupled models.

Implements Algorithms 2-3 from "Uncertainty on Discrete-Event System
Simulation" (VWD21). Wraps a CoupledModel and manages child engines
(Simulators or sub-Coordinators).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cadpya.engine.simulator import Simulator
from cadpya.modeling.interval import Interval

if TYPE_CHECKING:
    from cadpya.modeling.coupled import CoupledModel


@dataclass(frozen=True, slots=True)
class BranchAction:
    """One possible action in the current step."""

    engine_name: str
    limit: Interval[Any]


class Coordinator[T, Y]:
    """IA-DEVS Coordinator for a coupled model (Algorithms 2-3).

    Type parameters:
        T: base time type
        Y: base output type
    """

    __slots__ = (
        "_coupled_model",
        "_engines",
        "_influenced_by",
        "_t_last",
        "_t_next",
        "_zero_time",
    )

    def __init__(self, coupled_model: CoupledModel[T], zero_time: T) -> None:
        self._coupled_model = coupled_model
        self._zero_time = zero_time
        self._engines: dict[str, Simulator[Any, T, Any, Any] | Coordinator[T, Any]] = {}
        self._t_last: Interval[T] | None = None
        self._t_next: Interval[T] | None = None
        # Precompute: for each source engine, which destinations does it influence?
        self._influenced_by: dict[str, set[str]] = {}

    def init(self, t: Interval[T]) -> None:
        """Initialize all child engines from ComponentSpec (Algorithm 2 init)."""
        self._engines.clear()
        self._influenced_by.clear()

        for name, spec in self._coupled_model.components.items():
            if spec.is_atomic:
                assert spec.model_factory is not None
                assert spec.initial_state is not None
                assert spec.initial_elapsed is not None
                engine: Simulator[Any, T, Any, Any] | Coordinator[T, Any] = Simulator(
                    spec.model_factory, self._zero_time
                )
                engine.init(spec.initial_state, spec.initial_elapsed, t)  # type: ignore[call-arg]
            else:
                assert spec.coupled_model is not None
                engine = Coordinator(spec.coupled_model, self._zero_time)
                engine.init(t)
            self._engines[name] = engine

        # Build influenced_by: source → {destinations}
        for dest, sources in self._coupled_model.influencers.items():
            if dest == "self":
                continue  # EOC handled separately in _route
            for source in sources:
                if source == "self":
                    continue  # EIC handled in x_function
                if source not in self._influenced_by:
                    self._influenced_by[source] = set()
                self._influenced_by[source].add(dest)

        self._bound_ts()

    def _bound_ts(self) -> None:
        """Compute t_last and t_next from children (Algorithm 2 BoundTs)."""
        all_engines = list(self._engines.values())
        active = [eng for eng in all_engines if eng.t_next is not None]

        # t_last: max of all children's t_last
        self._t_last = self._compute_t_last(all_engines)

        if not active:
            self._t_next = None
            return

        self._t_next = self._compute_t_next(active)

    def _compute_t_last(
        self,
        engines: list[Simulator[Any, T, Any, Any] | Coordinator[T, Any]],
    ) -> Interval[T]:
        """Compute t_last as the max of all children's t_last."""
        # Lower of t_last: max of all lower bounds
        max_lo = engines[0].t_last.lower
        max_lo_closed = engines[0].t_last.lower_closed
        for eng in engines[1:]:
            tl = eng.t_last
            if tl.lower > max_lo:  # type: ignore[operator]
                max_lo = tl.lower
                max_lo_closed = tl.lower_closed
            elif tl.lower == max_lo:
                # Closed only if all at this value are closed
                if not tl.lower_closed:
                    max_lo_closed = False

        # Upper of t_last: max of all upper bounds
        max_hi = engines[0].t_last.upper
        max_hi_closed = engines[0].t_last.upper_closed
        for eng in engines[1:]:
            tl = eng.t_last
            if tl.upper > max_hi:  # type: ignore[operator]
                max_hi = tl.upper
                max_hi_closed = tl.upper_closed
            elif tl.upper == max_hi:
                # For upper of t_last: closed if any child includes it
                if tl.upper_closed:
                    max_hi_closed = True

        return Interval(
            max_lo,
            max_hi,
            lower_closed=max_lo_closed,
            upper_closed=max_hi_closed,
        )

    def _compute_t_next(
        self,
        active: list[Simulator[Any, T, Any, Any] | Coordinator[T, Any]],
    ) -> Interval[T]:
        """Compute t_next as the min of active children's t_next."""
        first_tn = active[0].t_next
        assert first_tn is not None

        min_lo = first_tn.lower
        min_lo_closed = first_tn.lower_closed
        min_lo_inf = first_tn.lower_inf

        min_hi = first_tn.upper
        min_hi_closed = first_tn.upper_closed
        min_hi_inf = first_tn.upper_inf

        for eng in active[1:]:
            tn = eng.t_next
            assert tn is not None

            # Min of lower bounds
            if tn.lower_inf == -1:
                min_lo = tn.lower
                min_lo_closed = tn.lower_closed
                min_lo_inf = -1
            elif min_lo_inf == -1:
                pass  # keep current
            elif tn.lower_inf == 1:
                pass  # +inf can't be min
            elif min_lo_inf == 1:
                min_lo = tn.lower
                min_lo_closed = tn.lower_closed
                min_lo_inf = tn.lower_inf
            elif tn.lower < min_lo:  # type: ignore[operator]
                min_lo = tn.lower
                min_lo_closed = tn.lower_closed
                min_lo_inf = 0
            elif tn.lower == min_lo:
                # Closed if any at this value is closed (we want the widest min)
                if tn.lower_closed:
                    min_lo_closed = True

            # Min of upper bounds
            if tn.upper_inf == -1:
                min_hi = tn.upper
                min_hi_closed = tn.upper_closed
                min_hi_inf = -1
            elif min_hi_inf == -1:
                pass
            elif tn.upper_inf == 1:
                pass  # +inf can't be min
            elif min_hi_inf == 1:
                min_hi = tn.upper
                min_hi_closed = tn.upper_closed
                min_hi_inf = tn.upper_inf
            elif tn.upper < min_hi:  # type: ignore[operator]
                min_hi = tn.upper
                min_hi_closed = tn.upper_closed
                min_hi_inf = 0
            elif tn.upper == min_hi:
                # For min of upper: closed only if all at this value are closed
                if not tn.upper_closed:
                    min_hi_closed = False

        return Interval(
            min_lo,
            min_hi,
            lower_closed=min_lo_closed,
            upper_closed=min_hi_closed,
            lower_inf=min_lo_inf,
            upper_inf=min_hi_inf,
        )

    def star_function(self, t: Interval[T]) -> Interval[Any] | None:
        """Process internal event as an Engine interface.

        Used when this Coordinator is a child of a parent Coordinator.
        Computes branches internally and executes the first non-skip action.
        Returns EOC output or None.
        """
        actions = self.compute_branches(t)
        if not actions:
            return None

        # Execute first non-skip action (skip actions have empty engine_name)
        for action in actions:
            if action.engine_name:
                return self.execute_branch(action)

        # All skip actions — execute first one
        return self.execute_branch(actions[0])

    def compute_branches(self, t: Interval[T]) -> list[BranchAction]:
        """Compute possible branches without side effects (Algorithm 3 logic).

        Returns a list of BranchAction. The Root Coordinator clones state
        and calls execute_branch on each.
        """
        if self._t_next is None:
            return []

        # 1. Find imminent engines (t_next intersects t)
        imminents = [
            name
            for name, eng in self._engines.items()
            if eng.t_next is not None and eng.t_next.intersects(t)
        ]

        if not imminents:
            return []

        # 2. Sort by << ordering: lower bound first, then upper bound
        def sort_key(name: str) -> tuple[Any, Any]:
            tn = self._engines[name].t_next
            assert tn is not None
            return (tn.lower, tn.upper)

        imminents.sort(key=sort_key)

        # 3. Compute limit: intersection of first imminent's t_next with t
        first_tn = self._engines[imminents[0]].t_next
        assert first_tn is not None
        limit = first_tn.intersection(t)

        # Restrict upper bound if later imminents have values beyond first
        if len(imminents) > 1:
            for name in imminents[1:]:
                eng_tn = self._engines[name].t_next
                assert eng_tn is not None
                # If this imminent has values strictly after first's lower
                if eng_tn.lower > first_tn.lower:  # type: ignore[operator]
                    # Restrict limit's upper to this engine's lower
                    limit = _restrict_upper(limit, eng_tn.lower, eng_tn.lower_closed)
                    break
                if eng_tn.lower == first_tn.lower and (
                    not eng_tn.lower_closed and first_tn.lower_closed
                ):
                    limit = _restrict_upper(limit, eng_tn.lower, eng_tn.lower_closed)
                    break

        # 4. Check if punctual
        if limit.is_punctual():
            # SELECT among candidates whose t_next intersects the limit
            candidates = frozenset(
                name
                for name in imminents
                if (tn_ := self._engines[name].t_next) is not None and tn_.intersects(limit)
            )
            chosen = self._coupled_model.select(candidates)

            branches: list[BranchAction] = []

            # Fork branch if limit is strictly inside chosen's t_next
            chosen_tn = self._engines[chosen].t_next
            assert chosen_tn is not None
            if limit != chosen_tn:
                # The "what if it doesn't fire at this exact point" branch
                # This branch subtracts the limit and recurses
                branches.append(BranchAction(engine_name="", limit=limit))

            # Main branch: advance chosen engine
            branches.append(BranchAction(engine_name=chosen, limit=limit))
            return branches
        # Non-punctual: one branch per imminent in the limit
        relevant = [
            name
            for name in imminents
            if (tn_ := self._engines[name].t_next) is not None and tn_.intersects(limit)
        ]
        return [BranchAction(engine_name=name, limit=limit) for name in relevant]

    def execute_branch(self, action: BranchAction) -> Interval[Any] | None:
        """Execute one branch action: route the chosen engine, update BoundTs.

        If action.engine_name is empty string, this is a "skip" branch
        (subtract limit from all imminents).
        """
        if action.engine_name == "":
            # Skip branch: subtract the punctual limit from imminent engines
            self._subtract_limit(action.limit)
            self._bound_ts()
            return None

        y = self._route(action.engine_name, action.limit)
        self._bound_ts()
        return y

    def _subtract_limit(self, limit: Interval[T]) -> None:
        """Subtract limit from all imminent engines' t_next.

        For engines whose t_next intersects the limit, create new interval
        excluding the limit point. For punctual limit [v,v], [a,b] becomes (v,b].
        """
        for eng in self._engines.values():
            if eng.t_next is not None and eng.t_next.intersects(limit):
                tn = eng.t_next
                if limit.is_punctual() and tn.lower == limit.lower:
                    # Punctual: exclude the point from lower bound
                    new_tn = Interval(
                        tn.lower,
                        tn.upper,
                        lower_closed=False,
                        upper_closed=tn.upper_closed,
                        lower_inf=tn.lower_inf,
                        upper_inf=tn.upper_inf,
                    )
                    # Force-set via object.__setattr__ since Interval is frozen
                    object.__setattr__(eng, "_t_next", new_tn)

    def _route(self, engine_name: str, t: Interval[T]) -> Interval[Any] | None:
        """Route engine's output to influenced engines (Algorithm 3 route)."""
        eng = self._engines[engine_name]
        y = eng.star_function(t)

        if y is None:
            return None

        # Route output to influenced engines (IC)
        for dest in self._influenced_by.get(engine_name, set()):
            z = self._coupled_model.translations[(engine_name, dest)]
            x_translated = z(y)
            self._engines[dest].x_function(x_translated, t)

        # Check for EOC (output to parent)
        eoc_sources = self._coupled_model.influencers.get("self", frozenset())
        if engine_name in eoc_sources:
            z_eoc = self._coupled_model.translations[(engine_name, "self")]
            return z_eoc(y)

        return None

    def x_function(self, x: Interval[Any], t: Interval[T]) -> None:
        """Route external input to EIC targets (Algorithm 2 x-function)."""
        for dest, sources in self._coupled_model.influencers.items():
            if "self" in sources and dest != "self":
                z = self._coupled_model.translations[("self", dest)]
                x_translated = z(x)
                self._engines[dest].x_function(x_translated, t)
        self._bound_ts()

    @property
    def t_last(self) -> Interval[T]:
        """Time of last processed event."""
        if self._t_last is None:
            msg = "Coordinator not initialized"
            raise RuntimeError(msg)
        return self._t_last

    @property
    def t_next(self) -> Interval[T] | None:
        """Time of next scheduled event, or None if all passive."""
        return self._t_next

    @property
    def engines(self) -> dict[str, Simulator[Any, T, Any, Any] | Coordinator[T, Any]]:
        """Access child engines."""
        return self._engines

    def __deepcopy__(self, memo: dict[int, Any]) -> Coordinator[T, Y]:
        """Deep copy sharing the immutable CoupledModel."""
        cls = type(self)
        result = cls.__new__(cls)
        memo[id(self)] = result
        object.__setattr__(result, "_coupled_model", self._coupled_model)
        object.__setattr__(result, "_zero_time", self._zero_time)
        object.__setattr__(result, "_engines", copy.deepcopy(self._engines, memo))
        object.__setattr__(result, "_t_last", copy.deepcopy(self._t_last, memo))
        object.__setattr__(result, "_t_next", copy.deepcopy(self._t_next, memo))
        object.__setattr__(result, "_influenced_by", copy.deepcopy(self._influenced_by, memo))
        return result


def _restrict_upper[T](iv: Interval[T], value: T, value_closed: bool) -> Interval[T]:
    """Restrict an interval's upper bound to not exceed value."""
    if iv.upper_inf == 1 or iv.upper > value:  # type: ignore[operator]
        return Interval(
            iv.lower,
            value,
            lower_closed=iv.lower_closed,
            upper_closed=not value_closed,  # open at boundary to exclude
            lower_inf=iv.lower_inf,
            upper_inf=0,
        )
    if iv.upper == value and iv.upper_closed and value_closed:
        return Interval(
            iv.lower,
            value,
            lower_closed=iv.lower_closed,
            upper_closed=False,  # open to exclude exact boundary
            lower_inf=iv.lower_inf,
            upper_inf=0,
        )
    return iv
