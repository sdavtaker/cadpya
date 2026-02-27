"""Counter IA-DEVS atomic model.

Discrete phase + count. Exercises intervals over enum-ordered states.

Behavior:
- Phase: passive or output (passive < output)
- Input events: add or reset (add < reset)
- Add event: increment count, stay passive
- Reset event: transition to output phase (ta = 0, immediate output)
- Internal transition: output count, reset to (passive, 0)
- Uncertain input [add, reset]: lower stays passive, upper becomes output
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from functools import total_ordering

from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

# Type aliases
type Time = Decimal

SCALE = 3
ZERO_TIME_VAL = Decimal.zero(3)


class Phase(enum.IntEnum):
    """Counter phase: passive or outputting."""

    PASSIVE = 0
    OUTPUT = 1


class InputEvent(enum.IntEnum):
    """Counter input events."""

    ADD = 0
    RESET = 1


@total_ordering
@dataclass(frozen=True, slots=True)
class CounterState:
    """Counter state: phase + accumulated count."""

    phase: Phase
    count: int

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, CounterState):
            return NotImplemented
        if self.phase != other.phase:
            return self.phase < other.phase
        return self.count < other.count

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CounterState):
            return NotImplemented
        return self.phase == other.phase and self.count == other.count

    def __hash__(self) -> int:
        return hash((self.phase, self.count))


type State = CounterState
type Input = InputEvent
type Output = int


class Counter:
    """Counter IA-DEVS atomic model.

    Counts incoming add events and outputs the count on reset.
    """

    __slots__ = ("_state", "_time")

    def __init__(self, initial_state: Interval[State], initial_time: Interval[Time]) -> None:
        self._state = initial_state
        self._time = initial_time

    def internal_transition(self) -> None:
        """Delta_int: reset to (passive, 0)."""
        reset = CounterState(Phase.PASSIVE, 0)
        self._state = Interval.closed(reset, reset)

    def external_transition(self, elapsed: Interval[Time], x: Interval[Input]) -> None:
        """Delta_ext: add increments count, reset transitions to output phase."""
        lo = self._state.lower
        hi = self._state.upper

        new_lo = _apply_input(lo, x.lower)
        new_hi = _apply_input(hi, x.upper)
        self._state = Interval.closed(new_lo, new_hi)

    def output(self) -> Interval[Output]:
        """Lambda: output the count."""
        return Interval.closed(self._state.lower.count, self._state.upper.count)

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


def _apply_input(state: CounterState, event: InputEvent) -> CounterState:
    """Apply a single input event to a single state."""
    match event:
        case InputEvent.ADD:
            return CounterState(state.phase, state.count + 1)
        case InputEvent.RESET:
            return CounterState(Phase.OUTPUT, state.count)
