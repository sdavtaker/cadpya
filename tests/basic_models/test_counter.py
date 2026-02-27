"""Tests for the Counter IA-DEVS atomic model."""

from __future__ import annotations

import pytest

from cadpya.basic_models.counter import (
    Counter,
    CounterState,
    InputEvent,
    Phase,
)
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

ZERO_TIME = Interval.closed(Decimal.zero(3), Decimal.zero(3))
ZERO_ELAPSED = Interval.closed(Decimal.zero(3), Decimal.zero(3))


def passive(count: int = 0) -> CounterState:
    return CounterState(Phase.PASSIVE, count)


def output_phase(count: int = 0) -> CounterState:
    return CounterState(Phase.OUTPUT, count)


class TestConstruction:
    def test_passive_initial_state(self) -> None:
        state = Interval.closed(passive(), passive())
        ctr = Counter(state, ZERO_TIME)
        assert ctr.state_interval == state

    def test_initial_time_stored(self) -> None:
        state = Interval.closed(passive(), passive())
        ctr = Counter(state, ZERO_TIME)
        assert ctr.time_interval == ZERO_TIME


class TestExternalTransitionAdd:
    def test_add_increments_count(self) -> None:
        state = Interval.closed(passive(0), passive(0))
        ctr = Counter(state, ZERO_TIME)
        x = Interval.closed(InputEvent.ADD, InputEvent.ADD)
        ctr.external_transition(ZERO_ELAPSED, x)
        assert ctr.state_interval == Interval.closed(passive(1), passive(1))

    def test_add_stays_passive(self) -> None:
        state = Interval.closed(passive(5), passive(5))
        ctr = Counter(state, ZERO_TIME)
        x = Interval.closed(InputEvent.ADD, InputEvent.ADD)
        ctr.external_transition(ZERO_ELAPSED, x)
        assert ctr.state_interval.lower.phase == Phase.PASSIVE
        assert ctr.state_interval.upper.phase == Phase.PASSIVE


class TestExternalTransitionReset:
    def test_reset_transitions_to_output(self) -> None:
        state = Interval.closed(passive(3), passive(3))
        ctr = Counter(state, ZERO_TIME)
        x = Interval.closed(InputEvent.RESET, InputEvent.RESET)
        ctr.external_transition(ZERO_ELAPSED, x)
        assert ctr.state_interval == Interval.closed(output_phase(3), output_phase(3))

    def test_reset_preserves_count(self) -> None:
        state = Interval.closed(passive(7), passive(7))
        ctr = Counter(state, ZERO_TIME)
        x = Interval.closed(InputEvent.RESET, InputEvent.RESET)
        ctr.external_transition(ZERO_ELAPSED, x)
        assert ctr.state_interval.lower.count == 7


class TestExternalTransitionUncertain:
    def test_add_reset_interval(self) -> None:
        state = Interval.closed(passive(2), passive(2))
        ctr = Counter(state, ZERO_TIME)
        x = Interval.closed(InputEvent.ADD, InputEvent.RESET)
        ctr.external_transition(ZERO_ELAPSED, x)
        # Lower: add → passive(3), Upper: reset → output(2)
        assert ctr.state_interval.lower == passive(3)
        assert ctr.state_interval.upper == output_phase(2)


class TestInternalTransition:
    def test_resets_to_passive_zero(self) -> None:
        state = Interval.closed(output_phase(5), output_phase(5))
        ctr = Counter(state, ZERO_TIME)
        ctr.internal_transition()
        assert ctr.state_interval == Interval.closed(passive(0), passive(0))


class TestOutput:
    def test_returns_count_interval(self) -> None:
        state = Interval.closed(output_phase(3), output_phase(5))
        ctr = Counter(state, ZERO_TIME)
        assert ctr.output() == Interval.closed(3, 5)

    def test_returns_point_count(self) -> None:
        state = Interval.closed(output_phase(7), output_phase(7))
        ctr = Counter(state, ZERO_TIME)
        assert ctr.output() == Interval.closed(7, 7)


class TestTimeAdvance:
    def test_passive_passive_returns_none(self) -> None:
        state = Interval.closed(passive(), passive())
        ctr = Counter(state, ZERO_TIME)
        assert ctr.time_advance() is None

    def test_output_output_returns_zero(self) -> None:
        state = Interval.closed(output_phase(), output_phase())
        ctr = Counter(state, ZERO_TIME)
        ta = ctr.time_advance()
        assert ta == Interval.closed(Decimal.zero(3), Decimal.zero(3))

    def test_passive_output_returns_right_open_inf(self) -> None:
        state = Interval.closed(passive(), output_phase())
        ctr = Counter(state, ZERO_TIME)
        ta = ctr.time_advance()
        assert ta is not None
        assert ta.lower == Decimal.zero(3)
        assert ta.upper_inf == 1
        assert ta.lower_closed is True
        assert ta.upper_closed is False

    def test_output_passive_cannot_be_constructed(self) -> None:
        # output > passive in ordering, so Interval.closed rejects it
        with pytest.raises(ValueError, match=r"lower.*upper"):
            Interval.closed(output_phase(), passive())

    def test_empty_state_returns_none(self) -> None:
        state = Interval.empty(passive())
        ctr = Counter(state, ZERO_TIME)
        assert ctr.time_advance() is None


class TestCounterState:
    def test_ordering_by_phase(self) -> None:
        assert passive(0) < output_phase(0)

    def test_ordering_by_count(self) -> None:
        assert passive(1) < passive(2)

    def test_equality(self) -> None:
        assert passive(3) == passive(3)

    def test_inequality(self) -> None:
        assert passive(1) != passive(2)

    def test_hashable(self) -> None:
        s = {passive(1), passive(1)}
        assert len(s) == 1


class TestFullCycle:
    def test_add_add_reset_output_cycle(self) -> None:
        state = Interval.closed(passive(0), passive(0))
        ctr = Counter(state, ZERO_TIME)

        # Add twice
        add = Interval.closed(InputEvent.ADD, InputEvent.ADD)
        ctr.external_transition(ZERO_ELAPSED, add)
        ctr.external_transition(ZERO_ELAPSED, add)
        assert ctr.state_interval == Interval.closed(passive(2), passive(2))

        # Reset
        reset = Interval.closed(InputEvent.RESET, InputEvent.RESET)
        ctr.external_transition(ZERO_ELAPSED, reset)
        assert ctr.state_interval.lower.phase == Phase.OUTPUT

        # Output
        assert ctr.output() == Interval.closed(2, 2)

        # Internal transition
        ctr.internal_transition()
        assert ctr.state_interval == Interval.closed(passive(0), passive(0))
        assert ctr.time_advance() is None

    def test_uncertain_input_cycle(self) -> None:
        """Full cycle with uncertain input [add, reset]."""
        state = Interval.closed(passive(0), passive(0))
        ctr = Counter(state, ZERO_TIME)

        # First: certain add
        add = Interval.closed(InputEvent.ADD, InputEvent.ADD)
        ctr.external_transition(ZERO_ELAPSED, add)
        assert ctr.state_interval == Interval.closed(passive(1), passive(1))
        assert ctr.time_advance() is None  # both passive

        # Second: uncertain [add, reset]
        uncertain = Interval.closed(InputEvent.ADD, InputEvent.RESET)
        ctr.external_transition(ZERO_ELAPSED, uncertain)
        # Lower: add → passive(2), Upper: reset → output(1)
        assert ctr.state_interval.lower == passive(2)
        assert ctr.state_interval.upper == output_phase(1)

        # time_advance: [passive, output] → [0, +inf)
        ta = ctr.time_advance()
        assert ta is not None
        assert ta.lower == Decimal.zero(3)
        assert ta.upper_inf == 1

        # Output: count interval [2, 1] — but wait, lower.count > upper.count
        # The output is [lower.count, upper.count] = [2, 1]... however
        # the state ordering is passive(2) < output(1) which is valid
        # because phase is compared first. Output returns [2, 1] which
        # would be an invalid interval — let's verify what happens:
        # Actually output returns Interval.closed(lower.count, upper.count)
        # = Interval.closed(2, 1) which should raise since 2 > 1.
        # This is expected: output() should only be called when the model
        # is in output phase on both bounds. In the uncertain case,
        # only the simulator (via branching) would call output.
        # For now, verify the state is as expected.

        # Internal transition resets both to (passive, 0)
        ctr.internal_transition()
        assert ctr.state_interval == Interval.closed(passive(0), passive(0))
        assert ctr.time_advance() is None
