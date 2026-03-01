"""Tests for the Accumulator IA-DEVS atomic model."""

from __future__ import annotations

import pytest

from cadpya.basic_models.accumulator import (
    ZERO_TIME_VAL,
    Accumulator,
    AccumulatorState,
    Phase,
)
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval


def d(s: str) -> Decimal:
    """Shorthand for Decimal(3, s)."""
    return Decimal(3, s)


ZERO_TIME = Interval.closed(Decimal.zero(3), Decimal.zero(3))
PASSIVE_ZERO = AccumulatorState(Phase.PASSIVE, 0)
INITIAL_STATE = Interval.closed(PASSIVE_ZERO, PASSIVE_ZERO)


class TestConstruction:
    def test_initial_state_stored(self) -> None:
        acc = Accumulator(INITIAL_STATE, ZERO_TIME)
        assert acc.state_interval == INITIAL_STATE

    def test_initial_time_stored(self) -> None:
        acc = Accumulator(INITIAL_STATE, ZERO_TIME)
        assert acc.time_interval == ZERO_TIME


class TestTimeAdvance:
    def test_passive_returns_none(self) -> None:
        acc = Accumulator(INITIAL_STATE, ZERO_TIME)
        assert acc.time_advance() is None

    def test_output_returns_zero(self) -> None:
        output_state = AccumulatorState(Phase.OUTPUT, 5)
        state = Interval.closed(output_state, output_state)
        acc = Accumulator(state, ZERO_TIME)
        assert acc.time_advance() == Interval.closed(ZERO_TIME_VAL, ZERO_TIME_VAL)

    def test_mixed_passive_output_returns_right_open_inf(self) -> None:
        lo = AccumulatorState(Phase.PASSIVE, 3)
        hi = AccumulatorState(Phase.OUTPUT, 5)
        state = Interval.closed(lo, hi)
        acc = Accumulator(state, ZERO_TIME)
        assert acc.time_advance() == Interval.right_open_inf(ZERO_TIME_VAL)

    def test_invalid_output_passive_raises(self) -> None:
        lo = AccumulatorState(Phase.OUTPUT, 5)
        hi = AccumulatorState(Phase.PASSIVE, 3)
        # Bypass Interval.closed validation to construct invalid state
        state = Interval(lo, hi, lower_closed=True, upper_closed=True)
        acc = Accumulator(state, ZERO_TIME)
        with pytest.raises(ValueError, match=r"Invalid state"):
            acc.time_advance()


class TestExternalTransition:
    def test_accumulates_input(self) -> None:
        acc = Accumulator(INITIAL_STATE, ZERO_TIME)
        elapsed = Interval.closed(d("0.100"), d("0.100"))
        x = Interval.closed(3, 3)
        acc.external_transition(elapsed, x)
        expected_lo = AccumulatorState(Phase.OUTPUT, 3)
        expected_hi = AccumulatorState(Phase.OUTPUT, 3)
        assert acc.state_interval == Interval.closed(expected_lo, expected_hi)

    def test_uncertain_input(self) -> None:
        acc = Accumulator(INITIAL_STATE, ZERO_TIME)
        elapsed = Interval.closed(d("0.100"), d("0.100"))
        x = Interval.closed(1, 3)
        acc.external_transition(elapsed, x)
        expected_lo = AccumulatorState(Phase.OUTPUT, 1)
        expected_hi = AccumulatorState(Phase.OUTPUT, 3)
        assert acc.state_interval == Interval.closed(expected_lo, expected_hi)

    def test_multiple_accumulations(self) -> None:
        acc = Accumulator(INITIAL_STATE, ZERO_TIME)
        elapsed = Interval.closed(d("0.100"), d("0.100"))
        acc.external_transition(elapsed, Interval.closed(5, 5))
        # Now in OUTPUT phase with total=5, do internal to go passive
        acc.internal_transition()
        # Accumulate again
        acc.external_transition(elapsed, Interval.closed(3, 3))
        expected_lo = AccumulatorState(Phase.OUTPUT, 8)
        expected_hi = AccumulatorState(Phase.OUTPUT, 8)
        assert acc.state_interval == Interval.closed(expected_lo, expected_hi)


class TestInternalTransition:
    def test_returns_to_passive(self) -> None:
        output_state = AccumulatorState(Phase.OUTPUT, 7)
        state = Interval.closed(output_state, output_state)
        acc = Accumulator(state, ZERO_TIME)
        acc.internal_transition()
        expected = AccumulatorState(Phase.PASSIVE, 7)
        assert acc.state_interval == Interval.closed(expected, expected)

    def test_preserves_total(self) -> None:
        lo = AccumulatorState(Phase.OUTPUT, 3)
        hi = AccumulatorState(Phase.OUTPUT, 5)
        state = Interval.closed(lo, hi)
        acc = Accumulator(state, ZERO_TIME)
        acc.internal_transition()
        expected_lo = AccumulatorState(Phase.PASSIVE, 3)
        expected_hi = AccumulatorState(Phase.PASSIVE, 5)
        assert acc.state_interval == Interval.closed(expected_lo, expected_hi)


class TestOutput:
    def test_outputs_total(self) -> None:
        lo = AccumulatorState(Phase.OUTPUT, 3)
        hi = AccumulatorState(Phase.OUTPUT, 7)
        state = Interval.closed(lo, hi)
        acc = Accumulator(state, ZERO_TIME)
        assert acc.output() == Interval.closed(3, 7)

    def test_punctual_output(self) -> None:
        s = AccumulatorState(Phase.OUTPUT, 5)
        state = Interval.closed(s, s)
        acc = Accumulator(state, ZERO_TIME)
        assert acc.output() == Interval.closed(5, 5)
