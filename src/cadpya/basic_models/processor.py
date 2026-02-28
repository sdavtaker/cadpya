"""Processor IA-DEVS atomic model.

Composite state: time-on-current-job (tocj) + job queue. Exercises
intervals over user-defined ordered structs.

From the paper (Processor_IA):
- State: (tocj: Decimal, qj: tuple[int, ...]) — tocj in [0, 0.250]
- Processing time: fixed 0.250s
- delta_int: dequeue front job, reset tocj to 0
- delta_ext: enqueue new job, update tocj += elapsed
- lambda: output = front of queue
- ta: [proc_time - tocj_upper, proc_time - tocj_lower] when non-empty
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering

from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

# Type aliases
type Time = Decimal
type Input = int
type Output = int

# Constants
SCALE = 3
PROCESSING_TIME = Decimal(3, "0.250")
ZERO_TOCJ = Decimal.zero(3)


@total_ordering
@dataclass(frozen=True, slots=True)
class ProcessorState:
    """Processor state: time-on-current-job + job queue."""

    tocj: Decimal
    qj: tuple[int, ...]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ProcessorState):
            return NotImplemented
        if self.tocj != other.tocj:
            return self.tocj < other.tocj
        if len(self.qj) != len(other.qj):
            return len(self.qj) < len(other.qj)
        return self.qj < other.qj

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProcessorState):
            return NotImplemented
        return self.tocj == other.tocj and self.qj == other.qj

    def __hash__(self) -> int:
        return hash((self.tocj, self.qj))


type State = ProcessorState


class Processor:
    """Processor IA-DEVS atomic model.

    Processes jobs from a FIFO queue with fixed processing time and
    uncertainty tracking through intervals.
    """

    __slots__ = ("_state", "_time")

    def __init__(self, initial_state: Interval[State], initial_time: Interval[Time]) -> None:
        self._state = initial_state
        self._time = initial_time

    def internal_transition(self) -> None:
        """Delta_int: dequeue front job, reset tocj to 0."""
        lo = self._state.lower
        hi = self._state.upper
        new_lo = ProcessorState(tocj=ZERO_TOCJ, qj=lo.qj[1:])
        new_hi = ProcessorState(tocj=ZERO_TOCJ, qj=hi.qj[1:])
        if not new_lo.qj and not new_hi.qj:
            self._state = Interval.empty(new_lo)
        elif not new_lo.qj:
            # Mixed: lower empty, upper has jobs
            self._state = Interval.closed(new_lo, new_hi)
        else:
            self._state = Interval.closed(new_lo, new_hi)

    def external_transition(self, elapsed: Interval[Time], x: Interval[Input]) -> None:
        """Delta_ext: enqueue new job, update tocj += elapsed."""
        if self._state.is_empty():
            # Was passive, now receiving input: start fresh with new job
            # tocj = 0 because no time has been spent on this new job yet
            new_lo = ProcessorState(tocj=ZERO_TOCJ, qj=(x.lower,))
            new_hi = ProcessorState(tocj=ZERO_TOCJ, qj=(x.upper,))
        else:
            lo = self._state.lower
            hi = self._state.upper
            new_lo = ProcessorState(tocj=lo.tocj + elapsed.lower, qj=(*lo.qj, x.lower))
            new_hi = ProcessorState(tocj=hi.tocj + elapsed.upper, qj=(*hi.qj, x.upper))
        self._state = Interval.closed(new_lo, new_hi)

    def output(self) -> Interval[Output]:
        """Lambda: output front job ID."""
        lo = self._state.lower
        hi = self._state.upper
        return Interval.closed(lo.qj[0], hi.qj[0])

    def time_advance(self) -> Interval[Time] | None:
        """TA: processing_time - tocj when queue non-empty, None when empty."""
        if self._state.is_empty():
            return None

        lo = self._state.lower
        hi = self._state.upper
        lo_empty = len(lo.qj) == 0
        hi_empty = len(hi.qj) == 0

        if lo_empty and hi_empty:
            return None

        if not lo_empty and not hi_empty:
            # Both have jobs: [proc_time - tocj_upper, proc_time - tocj_lower]
            ta_lo = PROCESSING_TIME - hi.tocj
            ta_hi = PROCESSING_TIME - lo.tocj
            return Interval.closed(ta_lo, ta_hi)

        # Mixed: lower empty, upper has jobs → [val, +inf)
        ta_lo = PROCESSING_TIME - hi.tocj
        return Interval.right_open_inf(ta_lo)

    @property
    def state_interval(self) -> Interval[State]:
        return self._state

    @property
    def time_interval(self) -> Interval[Time]:
        return self._time
