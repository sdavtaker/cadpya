"""Accumulator (InfiniteSum) IA-DEVS atomic model.

Accumulates integer inputs and immediately outputs the running sum.

Behavior:
- Phase: passive or output (passive < output)
- External transition: total += x, phase = OUTPUT
- Internal transition: phase = PASSIVE (total preserved)
- Output: running total interval
- TA: OUTPUT → [0, 0], PASSIVE → None, mixed → [0, +inf)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from functools import total_ordering

from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

# Type aliases
type Time = Decimal

ZERO_TIME_VAL = Decimal.zero(3)


class Phase(enum.IntEnum):
    """Accumulator phase: passive or outputting."""

    PASSIVE = 0
    OUTPUT = 1


@total_ordering
@dataclass(frozen=True, slots=True)
class AccumulatorState:
    """Accumulator state: phase + running total."""

    phase: Phase
    total: int

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, AccumulatorState):
            return NotImplemented
        if self.phase != other.phase:
            return self.phase < other.phase
        return self.total < other.total

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AccumulatorState):
            return NotImplemented
        return self.phase == other.phase and self.total == other.total

    def __hash__(self) -> int:
        return hash((self.phase, self.total))


type State = AccumulatorState
type Input = int
type Output = int


class Accumulator:
    """Accumulator IA-DEVS atomic model.

    Accumulates incoming integer inputs and outputs the running sum.
    """

    __slots__ = ("_state", "_time")

    def __init__(self, initial_state: Interval[State], initial_time: Interval[Time]) -> None:
        self._state = initial_state
        self._time = initial_time

    def internal_transition(self) -> None:
        """Delta_int: phase = PASSIVE, total preserved."""
        lo = self._state.lower
        hi = self._state.upper
        new_lo = AccumulatorState(Phase.PASSIVE, lo.total)
        new_hi = AccumulatorState(Phase.PASSIVE, hi.total)
        self._state = Interval.closed(new_lo, new_hi)

    def external_transition(self, elapsed: Interval[Time], x: Interval[Input]) -> None:
        """Delta_ext: total += x, phase = OUTPUT."""
        lo = self._state.lower
        hi = self._state.upper
        new_lo = AccumulatorState(Phase.OUTPUT, lo.total + x.lower)
        new_hi = AccumulatorState(Phase.OUTPUT, hi.total + x.upper)
        self._state = Interval.closed(new_lo, new_hi)

    def output(self) -> Interval[Output]:
        """Lambda: output the running total."""
        return Interval.closed(self._state.lower.total, self._state.upper.total)

    def time_advance(self) -> Interval[Time] | None:
        """TA: depends on phase combination of lower and upper bounds."""
        if self._state.is_empty():
            return None

        lo_phase = self._state.lower.phase
        hi_phase = self._state.upper.phase

        match (lo_phase, hi_phase):
            case (Phase.PASSIVE, Phase.PASSIVE):
                return None
            case (Phase.OUTPUT, Phase.OUTPUT):
                return Interval.closed(ZERO_TIME_VAL, ZERO_TIME_VAL)
            case (Phase.PASSIVE, Phase.OUTPUT):
                return Interval.right_open_inf(ZERO_TIME_VAL)
            case (Phase.OUTPUT, Phase.PASSIVE):
                msg = (
                    "Invalid state: lower phase OUTPUT > upper phase PASSIVE "
                    "violates interval ordering invariant"
                )
                raise ValueError(msg)
            case _:  # pragma: no cover
                msg = f"Unexpected phase combination: {lo_phase}, {hi_phase}"
                raise ValueError(msg)

    @property
    def state_interval(self) -> Interval[State]:
        return self._state

    @property
    def time_interval(self) -> Interval[Time]:
        return self._time
