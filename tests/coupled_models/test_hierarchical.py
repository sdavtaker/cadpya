"""Tests for Example 3: Hierarchical coupled model.

Two sub-coupled models (each with 2 generators) feeding one processor
at the top level. Semantically equivalent to the flat 4GP model.

Top-level:
    Left  = CoupledModel(G1, G2) --[Z_{Left,P}]--> P --[Z_{P,self}]--> (output)
    Right = CoupledModel(G3, G4) --[Z_{Right,P}]--/

Left:
    G1 --[Z_{G1,self}]--> (output)
    G2 --[Z_{G2,self}]--> (output)

Right:
    G3 --[Z_{G3,self}]--> (output)
    G4 --[Z_{G4,self}]--> (output)
"""

from __future__ import annotations

from cadpya.basic_models.generator import ZERO_STATE, Generator
from cadpya.basic_models.processor import ZERO_TOCJ, Processor, ProcessorState
from cadpya.modeling.component import ComponentSpec
from cadpya.modeling.coupled import CoupledModel
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def _select_alphabetical(candidates: frozenset[str]) -> str:
    return sorted(candidates)[0]


def _make_z_job(job_id: int):
    """Create Z function that maps any output to a job ID interval."""

    def translate(y: Interval) -> Interval:  # type: ignore[type-arg]
        return Interval.closed(job_id, job_id)

    return translate


def _identity(y: Interval) -> Interval:  # type: ignore[type-arg]
    return y


def make_left_model() -> CoupledModel[Decimal]:
    """Sub-coupled model: G1 and G2."""
    return CoupledModel(
        components={
            "G1": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G2": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
        },
        influencers={
            "G1": frozenset(),
            "G2": frozenset(),
            "self": frozenset({"G1", "G2"}),
        },
        translations={
            ("G1", "self"): _make_z_job(1),
            ("G2", "self"): _make_z_job(2),
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


def make_right_model() -> CoupledModel[Decimal]:
    """Sub-coupled model: G3 and G4."""
    return CoupledModel(
        components={
            "G3": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G4": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
        },
        influencers={
            "G3": frozenset(),
            "G4": frozenset(),
            "self": frozenset({"G3", "G4"}),
        },
        translations={
            ("G3", "self"): _make_z_job(3),
            ("G4", "self"): _make_z_job(4),
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


def make_hierarchical_model() -> CoupledModel[Decimal]:
    """Top-level coupled model with nested sub-coupled models."""
    left = make_left_model()
    right = make_right_model()
    empty_proc = ProcessorState(tocj=ZERO_TOCJ, qj=())

    return CoupledModel(
        components={
            "Left": ComponentSpec.coupled(left),
            "Right": ComponentSpec.coupled(right),
            "P": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
        },
        influencers={
            "Left": frozenset(),
            "Right": frozenset(),
            "P": frozenset({"Left", "Right"}),
            "self": frozenset({"P"}),
        },
        translations={
            ("Left", "P"): _identity,
            ("Right", "P"): _identity,
            ("P", "self"): _identity,
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


class TestSubCoupledModels:
    def test_left_validates(self) -> None:
        left = make_left_model()
        assert len(left.components) == 2
        assert set(left.components.keys()) == {"G1", "G2"}

    def test_right_validates(self) -> None:
        right = make_right_model()
        assert len(right.components) == 2
        assert set(right.components.keys()) == {"G3", "G4"}

    def test_left_eoc_sources(self) -> None:
        left = make_left_model()
        assert left.influencers["self"] == frozenset({"G1", "G2"})

    def test_right_eoc_sources(self) -> None:
        right = make_right_model()
        assert right.influencers["self"] == frozenset({"G3", "G4"})


class TestHierarchicalConstruction:
    def test_validates_successfully(self) -> None:
        model = make_hierarchical_model()
        assert len(model.components) == 3

    def test_component_names(self) -> None:
        model = make_hierarchical_model()
        assert set(model.components.keys()) == {"Left", "Right", "P"}

    def test_left_is_coupled(self) -> None:
        model = make_hierarchical_model()
        assert model.components["Left"].is_coupled
        assert model.components["Left"].coupled_model is not None

    def test_right_is_coupled(self) -> None:
        model = make_hierarchical_model()
        assert model.components["Right"].is_coupled

    def test_processor_is_atomic(self) -> None:
        model = make_hierarchical_model()
        assert model.components["P"].is_atomic

    def test_nested_left_has_two_generators(self) -> None:
        model = make_hierarchical_model()
        left = model.components["Left"].coupled_model
        assert left is not None
        assert len(left.components) == 2

    def test_nested_right_has_two_generators(self) -> None:
        model = make_hierarchical_model()
        right = model.components["Right"].coupled_model
        assert right is not None
        assert len(right.components) == 2


class TestHierarchicalInfluencers:
    def test_sub_models_have_no_influencers(self) -> None:
        model = make_hierarchical_model()
        assert model.influencers["Left"] == frozenset()
        assert model.influencers["Right"] == frozenset()

    def test_processor_influenced_by_both(self) -> None:
        model = make_hierarchical_model()
        assert model.influencers["P"] == frozenset({"Left", "Right"})

    def test_self_influenced_by_processor(self) -> None:
        model = make_hierarchical_model()
        assert model.influencers["self"] == frozenset({"P"})


class TestComponentSpecFactories:
    def test_atomic_factory(self) -> None:
        spec = ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME)
        assert spec.is_atomic
        assert not spec.is_coupled

    def test_coupled_factory(self) -> None:
        left = make_left_model()
        spec = ComponentSpec.coupled(left)
        assert spec.is_coupled
        assert not spec.is_atomic
        assert spec.coupled_model is left
