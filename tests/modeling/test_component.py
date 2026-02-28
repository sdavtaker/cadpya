"""Tests for ComponentSpec."""

from __future__ import annotations

import pytest

from cadpya.basic_models.counter import Counter, CounterState, Phase
from cadpya.basic_models.generator import ZERO_STATE, Generator
from cadpya.basic_models.processor import ZERO_TOCJ, Processor, ProcessorState
from cadpya.modeling.component import ComponentSpec
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


class TestAtomicSpec:
    def test_generator_spec(self) -> None:
        spec = ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME)
        assert spec.is_atomic
        assert not spec.is_coupled
        assert spec.model_factory is Generator
        assert spec.initial_state == ZERO_STATE
        assert spec.initial_elapsed == ZERO_TIME

    def test_processor_spec(self) -> None:
        empty = ProcessorState(tocj=ZERO_TOCJ, qj=())
        spec = ComponentSpec.atomic(Processor, Interval.empty(empty), ZERO_TIME)
        assert spec.is_atomic
        assert spec.initial_state == Interval.empty(empty)

    def test_counter_spec(self) -> None:
        state = Interval.closed(CounterState(Phase.PASSIVE, 0), CounterState(Phase.PASSIVE, 0))
        spec = ComponentSpec.atomic(Counter, state, ZERO_TIME)
        assert spec.is_atomic

    def test_frozen(self) -> None:
        spec = ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME)
        with pytest.raises(AttributeError):
            spec.model_factory = None  # type: ignore[misc]


class TestCoupledSpec:
    def test_coupled_spec(self) -> None:
        # Use a mock CoupledModel-like object for now
        from unittest.mock import MagicMock

        mock_coupled = MagicMock()
        spec = ComponentSpec.coupled(mock_coupled)
        assert spec.is_coupled
        assert not spec.is_atomic
        assert spec.coupled_model is mock_coupled
        assert spec.model_factory is None
        assert spec.initial_state is None
        assert spec.initial_elapsed is None


class TestValidation:
    def test_both_factory_and_coupled_raises(self) -> None:
        from unittest.mock import MagicMock

        with pytest.raises(ValueError, match="cannot have both"):
            ComponentSpec(
                model_factory=Generator,
                initial_state=ZERO_STATE,
                initial_elapsed=ZERO_TIME,
                coupled_model=MagicMock(),
            )

    def test_neither_factory_nor_coupled_raises(self) -> None:
        with pytest.raises(ValueError, match="must have either"):
            ComponentSpec(
                model_factory=None,
                initial_state=None,
                initial_elapsed=None,
                coupled_model=None,
            )

    def test_atomic_missing_state_raises(self) -> None:
        with pytest.raises(ValueError, match="requires initial_state"):
            ComponentSpec(
                model_factory=Generator,
                initial_state=None,
                initial_elapsed=ZERO_TIME,
            )

    def test_atomic_missing_elapsed_raises(self) -> None:
        with pytest.raises(ValueError, match="requires initial_state"):
            ComponentSpec(
                model_factory=Generator,
                initial_state=ZERO_STATE,
                initial_elapsed=None,
            )

    def test_coupled_with_state_raises(self) -> None:
        from unittest.mock import MagicMock

        with pytest.raises(ValueError, match="should not have"):
            ComponentSpec(
                model_factory=None,
                initial_state=ZERO_STATE,
                initial_elapsed=None,
                coupled_model=MagicMock(),
            )
