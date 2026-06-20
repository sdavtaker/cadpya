"""Tests for the IA-DEVS Simulator (Algorithm 1)."""

from __future__ import annotations

import pytest

from cadpya.basic_models.counter import (
    Counter,
    CounterState,
    InputEvent,
    Phase,
)
from cadpya.basic_models.generator import OUTPUT_VALUE, PERIOD, ZERO_STATE, Generator
from cadpya.basic_models.processor import (
    PROCESSING_TIME,
    ZERO_TOCJ,
    Processor,
    ProcessorState,
)
from cadpya.engine.simulator import Simulator
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval


def d(s: str) -> Decimal:
    return Decimal(3, s)


ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


class TestSimulatorInit:
    def test_not_initialized_raises_on_star(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        with pytest.raises(RuntimeError, match="not initialized"):
            sim.star_function(ZERO_TIME)

    def test_not_initialized_raises_on_x(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        with pytest.raises(RuntimeError, match="not initialized"):
            sim.x_function(ZERO_TIME, ZERO_TIME)

    def test_not_initialized_raises_on_t_last(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = sim.t_last

    def test_not_initialized_raises_on_model(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = sim.model


class TestGeneratorThroughSimulator:
    def test_init_from_zero(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)
        # t_last = t - q_time = [0,0] - [0,0] = [0,0]
        assert sim.t_last == ZERO_TIME
        # t_next = t_last + TA(state) = [0,0] + [0.997,1.005] = [0.997,1.005]
        assert sim.t_next == PERIOD

    def test_star_function_at_t_next(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)

        # Call star at t_next = [0.997, 1.005]
        y = sim.star_function(PERIOD)
        assert y == OUTPUT_VALUE

        # State should be reset to [0,0]
        assert sim.model.state_interval == ZERO_STATE

        # t_last = [0.997, 1.005]
        assert sim.t_last == PERIOD

        # t_next = t_last + TA([0,0]) = [0.997,1.005] + [0.997,1.005] = [1.994,2.010]
        assert sim.t_next == Interval.closed(d("1.994"), d("2.010"))

    def test_two_consecutive_stars(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)

        # First star
        sim.star_function(PERIOD)
        t_next_1 = sim.t_next
        assert t_next_1 is not None

        # Second star
        y2 = sim.star_function(t_next_1)
        assert y2 == OUTPUT_VALUE
        # t_next = [1.994,2.010] + [0.997,1.005] = [2.991,3.015]
        assert sim.t_next == Interval.closed(d("2.991"), d("3.015"))

    def test_star_invariant_violation(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)

        # t_next is [0.997, 1.005], call with [0.000, 0.000] which is not a subset
        with pytest.raises(ValueError, match=r"\*-function invariant violated"):
            sim.star_function(ZERO_TIME)

    def test_x_function_between_events(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)

        # External input at t=[0.500, 0.500]
        t = Interval.closed(d("0.500"), d("0.500"))
        x = Interval.closed(d("0.000"), d("0.000"))
        sim.x_function(x, t)

        # State should be [0,0] + elapsed=[0.500,0.500] = [0.500,0.500]
        assert sim.model.state_interval == Interval.closed(d("0.500"), d("0.500"))

        # t_last = [0.500, 0.500]
        assert sim.t_last == t

        # t_next = [0.500,0.500] + TA([0.500,0.500])
        # TA = [0.997,1.005] - [0.500,0.500] = [0.497,0.505]
        # t_next = [0.500,0.500] + [0.497,0.505] = [0.997,1.005]
        assert sim.t_next == Interval.closed(d("0.997"), d("1.005"))


class TestProcessorThroughSimulator:
    def test_init_passive(self) -> None:
        empty = ProcessorState(tocj=ZERO_TOCJ, qj=())
        sim: Simulator[ProcessorState, Decimal, int, int] = Simulator(Processor, ZERO)
        sim.init(Interval.empty(empty), ZERO_TIME, ZERO_TIME)
        assert sim.t_next is None

    def test_star_on_passive_raises(self) -> None:
        empty = ProcessorState(tocj=ZERO_TOCJ, qj=())
        sim: Simulator[ProcessorState, Decimal, int, int] = Simulator(Processor, ZERO)
        sim.init(Interval.empty(empty), ZERO_TIME, ZERO_TIME)
        with pytest.raises(ValueError, match="passive"):
            sim.star_function(ZERO_TIME)

    def test_x_wakes_passive_then_star(self) -> None:
        empty = ProcessorState(tocj=ZERO_TOCJ, qj=())
        sim: Simulator[ProcessorState, Decimal, int, int] = Simulator(Processor, ZERO)
        sim.init(Interval.empty(empty), ZERO_TIME, ZERO_TIME)

        # External input: enqueue job 1
        sim.x_function(Interval.closed(1, 1), ZERO_TIME)

        # t_next should be [0.250, 0.250]
        assert sim.t_next == Interval.closed(PROCESSING_TIME, PROCESSING_TIME)

        # Star: output job 1
        t_star = Interval.closed(d("0.250"), d("0.250"))
        y = sim.star_function(t_star)
        assert y == Interval.closed(1, 1)

        # After processing, queue empty → passive
        assert sim.t_next is None

    def test_two_jobs_sequential(self) -> None:
        empty = ProcessorState(tocj=ZERO_TOCJ, qj=())
        sim: Simulator[ProcessorState, Decimal, int, int] = Simulator(Processor, ZERO)
        sim.init(Interval.empty(empty), ZERO_TIME, ZERO_TIME)

        # Enqueue job 1 at t=0
        sim.x_function(Interval.closed(1, 1), ZERO_TIME)

        # Enqueue job 2 at t=0.100
        t_ext = Interval.closed(d("0.100"), d("0.100"))
        sim.x_function(Interval.closed(2, 2), t_ext)

        # t_next should account for tocj=0.100 on job 1
        # ta = [0.250-0.100, 0.250-0.100] = [0.150, 0.150]
        # t_next = [0.100,0.100] + [0.150,0.150] = [0.250, 0.250]
        assert sim.t_next == Interval.closed(d("0.250"), d("0.250"))

        # Star: output job 1
        y1 = sim.star_function(Interval.closed(d("0.250"), d("0.250")))
        assert y1 == Interval.closed(1, 1)

        # Job 2 still in queue → not passive
        assert sim.t_next is not None


class TestCounterThroughSimulator:
    def test_init_passive(self) -> None:
        state = Interval.closed(CounterState(Phase.PASSIVE, 0), CounterState(Phase.PASSIVE, 0))
        sim: Simulator[CounterState, Decimal, InputEvent, int] = Simulator(Counter, ZERO)
        sim.init(state, ZERO_TIME, ZERO_TIME)
        assert sim.t_next is None

    def test_add_stays_passive(self) -> None:
        state = Interval.closed(CounterState(Phase.PASSIVE, 0), CounterState(Phase.PASSIVE, 0))
        sim: Simulator[CounterState, Decimal, InputEvent, int] = Simulator(Counter, ZERO)
        sim.init(state, ZERO_TIME, ZERO_TIME)

        sim.x_function(Interval.closed(InputEvent.ADD, InputEvent.ADD), ZERO_TIME)
        assert sim.t_next is None

    def test_reset_then_immediate_star(self) -> None:
        state = Interval.closed(CounterState(Phase.PASSIVE, 0), CounterState(Phase.PASSIVE, 0))
        sim: Simulator[CounterState, Decimal, InputEvent, int] = Simulator(Counter, ZERO)
        sim.init(state, ZERO_TIME, ZERO_TIME)

        # Add twice
        add = Interval.closed(InputEvent.ADD, InputEvent.ADD)
        sim.x_function(add, ZERO_TIME)
        sim.x_function(add, ZERO_TIME)

        # Reset
        reset = Interval.closed(InputEvent.RESET, InputEvent.RESET)
        sim.x_function(reset, ZERO_TIME)

        # t_next = [0, 0] (immediate output)
        assert sim.t_next == ZERO_TIME

        # Star: output count = 2
        y = sim.star_function(ZERO_TIME)
        assert y == Interval.closed(2, 2)

        # After internal transition: passive
        assert sim.t_next is None


class TestElapsedTimeComputation:
    def test_normal_case(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)

        # t_last = [0,0], t = [0.500, 0.600]
        # elapsed = [0.500-0.000, 0.600-0.000] = [0.500, 0.600]
        t = Interval.closed(d("0.500"), d("0.600"))
        x = Interval.closed(d("0.000"), d("0.000"))
        sim.x_function(x, t)
        assert sim.model.state_interval == Interval.closed(d("0.500"), d("0.600"))

    def test_non_trivial_intervals(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)

        # First star to advance t_last
        sim.star_function(PERIOD)
        # Now t_last = [0.997, 1.005]

        # External at t = [1.500, 1.600]
        # elapsed upper = 1.600 - 0.997 = 0.603
        # elapsed lower = 1.500 - 1.005 = 0.495
        t = Interval.closed(d("1.500"), d("1.600"))
        x = Interval.closed(d("0.000"), d("0.000"))
        sim.x_function(x, t)
        # State was [0,0] after star. Now state = [0,0] + [0.495, 0.603] = [0.495, 0.603]
        assert sim.model.state_interval == Interval.closed(d("0.495"), d("0.603"))

    def test_confluent_case(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)

        # t_last = [0,0], t = [0,0] (same point, intersects)
        # confluent: elapsed lower = 0, closed
        x = Interval.closed(d("0.000"), d("0.000"))
        sim.x_function(x, ZERO_TIME)
        # elapsed = [0, 0], state = [0,0] + [0,0] = [0,0]
        assert sim.model.state_interval == ZERO_STATE

    def test_confluent_overlapping_intervals(self) -> None:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)

        # Star at PERIOD → t_last = [0.997, 1.005]
        sim.star_function(PERIOD)

        # External at t = [1.000, 1.010] which overlaps t_last = [0.997, 1.005]
        # confluent: elapsed lower = 0 (clamped)
        # elapsed upper = 1.010 - 0.997 = 0.013
        t = Interval.closed(d("1.000"), d("1.010"))
        x = Interval.closed(d("0.000"), d("0.000"))
        sim.x_function(x, t)
        # State was [0,0], now = [0,0] + [0.000, 0.013] = [0.000, 0.013]
        assert sim.model.state_interval == Interval.closed(d("0.000"), d("0.013"))


class TestSimulatorEngineEquals:
    def _make_sim(self) -> Simulator[Decimal, Decimal, Decimal, Decimal]:
        sim: Simulator[Decimal, Decimal, Decimal, Decimal] = Simulator(Generator, ZERO)
        sim.init(ZERO_STATE, ZERO_TIME, ZERO_TIME)
        return sim

    def test_equal_to_itself(self) -> None:
        sim = self._make_sim()
        assert sim.engine_equals(sim)

    def test_equal_to_fresh_copy(self) -> None:
        a = self._make_sim()
        b = self._make_sim()
        assert a.engine_equals(b)

    def test_not_equal_after_state_change(self) -> None:
        a = self._make_sim()
        b = self._make_sim()
        b.star_function(PERIOD)
        assert not a.engine_equals(b)

    def test_not_equal_to_non_simulator(self) -> None:
        sim = self._make_sim()
        assert not sim.engine_equals("not a simulator")

    def test_not_equal_when_t_last_differs(self) -> None:
        a = self._make_sim()
        b = self._make_sim()
        b.star_function(PERIOD)
        b2 = self._make_sim()
        assert not a.engine_equals(b)
        assert b2.engine_equals(a)
