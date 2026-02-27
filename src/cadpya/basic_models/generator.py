"""Generator IA-DEVS atomic model.

The simplest IA-DEVS model: scalar state representing accumulated time
since last output. Produces periodic output with uncertainty intervals.

From the paper (Generator_IA):
- State: accumulated time since last output, in [0, 1.005]
- Period: [0.997, 1.005] (uncertainty in tick frequency)
- Output: [1.997, 2.003] (uncertainty in output value)
- delta_int: reset state to [0, 0]
- delta_ext: state = state + elapsed (track time, ignore input)
- lambda: always [1.997, 2.003]
- ta: period - state, clamped to [0, +inf)
"""

from __future__ import annotations

from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

# Type aliases used in method signatures for clarity
type State = Decimal
type Time = Decimal
type Input = Decimal
type Output = Decimal

# Constants
SCALE = 3
PERIOD = Interval.closed(Decimal(3, "0.997"), Decimal(3, "1.005"))
OUTPUT_VALUE = Interval.closed(Decimal(3, "1.997"), Decimal(3, "2.003"))
ZERO_STATE = Interval.closed(Decimal.zero(3), Decimal.zero(3))
STATE_UPPER_BOUND = Decimal(3, "1.005")


class Generator:
    """Generator IA-DEVS atomic model.

    Periodic output producer with uncertainty in period and output value.
    """

    __slots__ = ("_state", "_time")

    def __init__(self, initial_state: Interval[State], initial_time: Interval[Time]) -> None:
        self._state = initial_state
        self._time = initial_time

    def internal_transition(self) -> None:
        """Delta_int: reset state to [0, 0] after output."""
        self._state = ZERO_STATE

    def external_transition(self, elapsed: Interval[Time], x: Interval[Input]) -> None:
        """Delta_ext: state = state + elapsed (ignore input)."""
        self._state = self._state + elapsed

    def output(self) -> Interval[Output]:
        """Lambda: always produce [1.997, 2.003]."""
        return OUTPUT_VALUE

    def time_advance(self) -> Interval[Time] | None:
        """TA: period - state. Generator never becomes passive."""
        return PERIOD - self._state

    @property
    def state_interval(self) -> Interval[State]:
        return self._state

    @property
    def time_interval(self) -> Interval[Time]:
        return self._time
