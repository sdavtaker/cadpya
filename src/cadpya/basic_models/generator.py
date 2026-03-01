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

from typing import TYPE_CHECKING

from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

if TYPE_CHECKING:
    from collections.abc import Callable

# Type aliases used in method signatures for clarity
type State = Decimal
type Time = Decimal
type Input = Decimal
type Output = Decimal

# Constants (defaults)
SCALE = 3
PERIOD = Interval.closed(Decimal(3, "0.997"), Decimal(3, "1.005"))
OUTPUT_VALUE = Interval.closed(Decimal(3, "1.997"), Decimal(3, "2.003"))
ZERO_STATE = Interval.closed(Decimal.zero(3), Decimal.zero(3))
STATE_UPPER_BOUND = Decimal(3, "1.005")


class Generator:
    """Generator IA-DEVS atomic model.

    Periodic output producer with uncertainty in period and output value.
    """

    __slots__ = ("_output_value", "_period", "_state", "_time")

    def __init__(self, initial_state: Interval[State], initial_time: Interval[Time]) -> None:
        self._state = initial_state
        self._time = initial_time
        self._period = PERIOD
        self._output_value = OUTPUT_VALUE

    def internal_transition(self) -> None:
        """Delta_int: reset state to [0, 0] after output."""
        self._state = ZERO_STATE

    def external_transition(self, elapsed: Interval[Time], x: Interval[Input]) -> None:
        """Delta_ext: state = state + elapsed (ignore input)."""
        self._state = self._state + elapsed

    def output(self) -> Interval[Output]:
        """Lambda: produce output value interval."""
        return self._output_value

    def time_advance(self) -> Interval[Time] | None:
        """TA: period - state. Generator never becomes passive."""
        return self._period - self._state

    @property
    def state_interval(self) -> Interval[State]:
        return self._state

    @property
    def time_interval(self) -> Interval[Time]:
        return self._time


def make_generator_factory(
    period: Interval[Decimal],
    output_value: Interval[Decimal],
) -> Callable[[Interval[State], Interval[Time]], Generator]:
    """Create a factory that builds Generators with custom period and output.

    Args:
        period: custom period interval (replaces default PERIOD)
        output_value: custom output value interval (replaces default OUTPUT_VALUE)

    Returns:
        A callable ``(initial_state, initial_time) -> Generator`` with the
        given period and output_value baked in.
    """

    def factory(initial_state: Interval[State], initial_time: Interval[Time]) -> Generator:
        gen = Generator(initial_state, initial_time)
        object.__setattr__(gen, "_period", period)
        object.__setattr__(gen, "_output_value", output_value)
        return gen

    return factory
