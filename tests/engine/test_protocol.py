"""Tests for the AtomicModel protocol."""

from __future__ import annotations

from cadpya.basic_models.counter import Counter, CounterState, Phase
from cadpya.basic_models.generator import ZERO_STATE, Generator
from cadpya.basic_models.processor import ZERO_TOCJ, Processor, ProcessorState
from cadpya.engine.protocol import AtomicModel
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

ZERO_TIME = Interval.closed(Decimal.zero(3), Decimal.zero(3))


class TestProtocolConformance:
    def test_generator_satisfies_protocol(self) -> None:
        gen = Generator(ZERO_STATE, ZERO_TIME)
        assert isinstance(gen, AtomicModel)

    def test_processor_satisfies_protocol(self) -> None:
        empty = ProcessorState(tocj=ZERO_TOCJ, qj=())
        proc = Processor(Interval.empty(empty), ZERO_TIME)
        assert isinstance(proc, AtomicModel)

    def test_counter_satisfies_protocol(self) -> None:
        state = Interval.closed(CounterState(Phase.PASSIVE, 0), CounterState(Phase.PASSIVE, 0))
        ctr = Counter(state, ZERO_TIME)
        assert isinstance(ctr, AtomicModel)

    def test_plain_object_does_not_satisfy(self) -> None:
        assert not isinstance(42, AtomicModel)

    def test_missing_method_does_not_satisfy(self) -> None:
        class Incomplete:
            def internal_transition(self) -> None: ...

        assert not isinstance(Incomplete(), AtomicModel)
