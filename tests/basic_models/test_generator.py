"""Tests for the Generator IA-DEVS atomic model."""

from __future__ import annotations

from cadpya.basic_models.generator import OUTPUT_VALUE, PERIOD, ZERO_STATE, Generator
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval


def d(s: str) -> Decimal:
    """Shorthand for Decimal(3, s)."""
    return Decimal(3, s)


ZERO_TIME = Interval.closed(Decimal.zero(3), Decimal.zero(3))


class TestConstruction:
    def test_initial_state_stored(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        assert gen.state_interval == ZERO_STATE

    def test_initial_time_stored(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        assert gen.time_interval == ZERO_TIME


class TestTimeAdvance:
    def test_from_zero_state(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        ta = gen.time_advance()
        # period - [0, 0] = period = [0.997, 1.005]
        assert ta == PERIOD

    def test_from_partial_state(self) -> None:
        state = Interval.closed(d("0.100"), d("0.200"))
        gen = Generator(state, ZERO_TIME)
        ta = gen.time_advance()
        # [0.997, 1.005] - [0.100, 0.200] = [0.997-0.200, 1.005-0.100] = [0.797, 0.905]
        assert ta == Interval.closed(d("0.797"), d("0.905"))

    def test_never_returns_none(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        assert gen.time_advance() is not None


class TestOutput:
    def test_always_returns_output_interval(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        assert gen.output() == OUTPUT_VALUE

    def test_output_independent_of_state(self) -> None:
        state = Interval.closed(d("0.500"), d("0.600"))
        gen = Generator(state, ZERO_TIME)
        assert gen.output() == OUTPUT_VALUE


class TestInternalTransition:
    def test_resets_state_to_zero(self) -> None:
        state = Interval.closed(d("0.500"), d("0.600"))
        gen = Generator(state, ZERO_TIME)
        gen.internal_transition()
        assert gen.state_interval == ZERO_STATE


class TestExternalTransition:
    def test_adds_elapsed_to_state(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        elapsed = Interval.closed(d("0.500"), d("0.500"))
        x = Interval.closed(d("0.000"), d("0.000"))  # ignored
        gen.external_transition(elapsed, x)
        assert gen.state_interval == Interval.closed(d("0.500"), d("0.500"))

    def test_accumulates_elapsed(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        elapsed1 = Interval.closed(d("0.300"), d("0.400"))
        elapsed2 = Interval.closed(d("0.100"), d("0.200"))
        x = Interval.closed(d("0.000"), d("0.000"))
        gen.external_transition(elapsed1, x)
        gen.external_transition(elapsed2, x)
        # [0.300, 0.400] + [0.100, 0.200] = [0.400, 0.600]
        assert gen.state_interval == Interval.closed(d("0.400"), d("0.600"))

    def test_ignores_input(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        elapsed = Interval.closed(d("0.100"), d("0.100"))
        x = Interval.closed(d("999.000"), d("999.000"))
        gen.external_transition(elapsed, x)
        # State only affected by elapsed, not x
        assert gen.state_interval == Interval.closed(d("0.100"), d("0.100"))


class TestFullCycle:
    def test_init_output_internal_cycle(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)

        # Initial ta
        ta = gen.time_advance()
        assert ta == PERIOD

        # Output
        out = gen.output()
        assert out == OUTPUT_VALUE

        # Internal transition resets
        gen.internal_transition()
        assert gen.state_interval == ZERO_STATE

        # ta is back to period
        assert gen.time_advance() == PERIOD
