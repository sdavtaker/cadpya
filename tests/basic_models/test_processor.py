"""Tests for the Processor IA-DEVS atomic model."""

from __future__ import annotations

from cadpya.basic_models.processor import (
    PROCESSING_TIME,
    ZERO_TOCJ,
    Processor,
    ProcessorState,
)
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval


def d(s: str) -> Decimal:
    """Shorthand for Decimal(3, s)."""
    return Decimal(3, s)


ZERO_TIME = Interval.closed(Decimal.zero(3), Decimal.zero(3))
EMPTY_STATE = ProcessorState(tocj=ZERO_TOCJ, qj=())


class TestConstruction:
    def test_empty_queue_is_passive(self) -> None:
        state = Interval.empty(EMPTY_STATE)
        proc = Processor(state, ZERO_TIME)
        assert proc.time_advance() is None

    def test_initial_state_stored(self) -> None:
        s = ProcessorState(tocj=ZERO_TOCJ, qj=(1,))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        assert proc.state_interval == state


class TestExternalTransition:
    def test_enqueue_first_job_from_passive(self) -> None:
        state = Interval.empty(EMPTY_STATE)
        proc = Processor(state, ZERO_TIME)
        elapsed = Interval.closed(d("0.000"), d("0.000"))
        x = Interval.closed(1, 1)
        proc.external_transition(elapsed, x)
        expected_s = ProcessorState(tocj=ZERO_TOCJ, qj=(1,))
        assert proc.state_interval == Interval.closed(expected_s, expected_s)
        # ta should be [0.250, 0.250]
        assert proc.time_advance() == Interval.closed(PROCESSING_TIME, PROCESSING_TIME)

    def test_enqueue_second_job(self) -> None:
        s = ProcessorState(tocj=d("0.100"), qj=(1,))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        elapsed = Interval.closed(d("0.050"), d("0.050"))
        x = Interval.closed(2, 2)
        proc.external_transition(elapsed, x)
        expected_s = ProcessorState(tocj=d("0.150"), qj=(1, 2))
        assert proc.state_interval == Interval.closed(expected_s, expected_s)

    def test_enqueue_preserves_order(self) -> None:
        s = ProcessorState(tocj=ZERO_TOCJ, qj=(10,))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        elapsed = Interval.closed(d("0.000"), d("0.000"))
        proc.external_transition(elapsed, Interval.closed(20, 20))
        proc.external_transition(elapsed, Interval.closed(30, 30))
        assert proc.state_interval.lower.qj == (10, 20, 30)


class TestOutput:
    def test_returns_front_job(self) -> None:
        s = ProcessorState(tocj=ZERO_TOCJ, qj=(42,))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        assert proc.output() == Interval.closed(42, 42)

    def test_returns_front_with_multiple_jobs(self) -> None:
        s = ProcessorState(tocj=ZERO_TOCJ, qj=(10, 20, 30))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        assert proc.output() == Interval.closed(10, 10)

    def test_returns_interval_over_different_fronts(self) -> None:
        lo = ProcessorState(tocj=ZERO_TOCJ, qj=(1,))
        hi = ProcessorState(tocj=ZERO_TOCJ, qj=(5,))
        state = Interval.closed(lo, hi)
        proc = Processor(state, ZERO_TIME)
        assert proc.output() == Interval.closed(1, 5)


class TestInternalTransition:
    def test_dequeues_front_job(self) -> None:
        s = ProcessorState(tocj=d("0.250"), qj=(1, 2))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        proc.internal_transition()
        expected = ProcessorState(tocj=ZERO_TOCJ, qj=(2,))
        assert proc.state_interval == Interval.closed(expected, expected)

    def test_last_job_dequeued_becomes_passive(self) -> None:
        s = ProcessorState(tocj=d("0.250"), qj=(1,))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        proc.internal_transition()
        assert proc.time_advance() is None

    def test_resets_tocj(self) -> None:
        s = ProcessorState(tocj=d("0.200"), qj=(1, 2))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        proc.internal_transition()
        assert proc.state_interval.lower.tocj == ZERO_TOCJ


class TestTimeAdvance:
    def test_fresh_job_returns_full_processing_time(self) -> None:
        s = ProcessorState(tocj=ZERO_TOCJ, qj=(1,))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        assert proc.time_advance() == Interval.closed(PROCESSING_TIME, PROCESSING_TIME)

    def test_with_elapsed_tocj(self) -> None:
        s = ProcessorState(tocj=d("0.100"), qj=(1,))
        state = Interval.closed(s, s)
        proc = Processor(state, ZERO_TIME)
        # ta = [0.250 - 0.100, 0.250 - 0.100] = [0.150, 0.150]
        assert proc.time_advance() == Interval.closed(d("0.150"), d("0.150"))

    def test_with_interval_tocj(self) -> None:
        lo = ProcessorState(tocj=d("0.050"), qj=(1,))
        hi = ProcessorState(tocj=d("0.150"), qj=(1,))
        state = Interval.closed(lo, hi)
        proc = Processor(state, ZERO_TIME)
        # ta = [0.250 - 0.150, 0.250 - 0.050] = [0.100, 0.200]
        assert proc.time_advance() == Interval.closed(d("0.100"), d("0.200"))

    def test_mixed_queue_case(self) -> None:
        lo = ProcessorState(tocj=ZERO_TOCJ, qj=())  # lower has no jobs
        hi = ProcessorState(tocj=d("0.100"), qj=(1,))  # upper has a job
        state = Interval.closed(lo, hi)
        proc = Processor(state, ZERO_TIME)
        ta = proc.time_advance()
        # Mixed: [0.250 - 0.100, +inf) = [0.150, +inf)
        assert ta is not None
        assert ta.lower == d("0.150")
        assert ta.upper_inf == 1


class TestProcessorState:
    def test_ordering_by_tocj(self) -> None:
        a = ProcessorState(tocj=d("0.100"), qj=(1,))
        b = ProcessorState(tocj=d("0.200"), qj=(1,))
        assert a < b

    def test_ordering_by_queue_size(self) -> None:
        a = ProcessorState(tocj=ZERO_TOCJ, qj=(1,))
        b = ProcessorState(tocj=ZERO_TOCJ, qj=(1, 2))
        assert a < b

    def test_ordering_by_queue_elements(self) -> None:
        a = ProcessorState(tocj=ZERO_TOCJ, qj=(1, 2))
        b = ProcessorState(tocj=ZERO_TOCJ, qj=(1, 3))
        assert a < b

    def test_equality(self) -> None:
        a = ProcessorState(tocj=d("0.100"), qj=(1, 2))
        b = ProcessorState(tocj=d("0.100"), qj=(1, 2))
        assert a == b

    def test_hashable(self) -> None:
        s = ProcessorState(tocj=ZERO_TOCJ, qj=(1,))
        assert {s, s} == {s}
