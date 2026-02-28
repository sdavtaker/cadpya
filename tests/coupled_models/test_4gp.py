"""Tests for Example 2: Four Generators + Processor (4GP).

The paper's case study: 4 Generators feeding 1 Processor.

    G1 --[Z_{G1,P}]--> P --[Z_{P,self}]--> (output)
    G2 --[Z_{G2,P}]--/
    G3 --[Z_{G3,P}]--/
    G4 --[Z_{G4,P}]--/
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cadpya.basic_models.generator import OUTPUT_VALUE, ZERO_STATE, Generator
from cadpya.basic_models.processor import ZERO_TOCJ, Processor, ProcessorState
from cadpya.modeling.component import ComponentSpec
from cadpya.modeling.coupled import CoupledModel
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

if TYPE_CHECKING:
    from collections.abc import Callable

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def _select_alphabetical(candidates: frozenset[str]) -> str:
    return sorted(candidates)[0]


def _make_z_gen_proc(job_id: int) -> Callable[[Interval[Any]], Interval[Any]]:
    """Create Z_{Gi,P}: Generator output → Processor input (job_id)."""

    def translate(y: Interval) -> Interval:  # type: ignore[type-arg]
        return Interval.closed(job_id, job_id)

    return translate


def _z_p_self(y: Interval) -> Interval:  # type: ignore[type-arg]
    """Z_{P,self}: identity."""
    return y


def make_4gp_model() -> CoupledModel[Decimal]:
    """Build the 4GP coupled model (paper case study)."""
    empty_proc = ProcessorState(tocj=ZERO_TOCJ, qj=())
    return CoupledModel(
        components={
            "G1": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G2": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G3": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G4": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "P": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
        },
        influencers={
            "G1": frozenset(),
            "G2": frozenset(),
            "G3": frozenset(),
            "G4": frozenset(),
            "P": frozenset({"G1", "G2", "G3", "G4"}),
            "self": frozenset({"P"}),
        },
        translations={
            ("G1", "P"): _make_z_gen_proc(1),
            ("G2", "P"): _make_z_gen_proc(2),
            ("G3", "P"): _make_z_gen_proc(3),
            ("G4", "P"): _make_z_gen_proc(4),
            ("P", "self"): _z_p_self,
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


class TestFourGPConstruction:
    def test_validates_successfully(self) -> None:
        model = make_4gp_model()
        assert len(model.components) == 5

    def test_component_names(self) -> None:
        model = make_4gp_model()
        assert set(model.components.keys()) == {"G1", "G2", "G3", "G4", "P"}

    def test_all_generators_are_atomic(self) -> None:
        model = make_4gp_model()
        for name in ("G1", "G2", "G3", "G4"):
            assert model.components[name].is_atomic
            assert model.components[name].model_factory is Generator


class TestFourGPInfluencers:
    def test_generators_have_no_influencers(self) -> None:
        model = make_4gp_model()
        for name in ("G1", "G2", "G3", "G4"):
            assert model.influencers[name] == frozenset()

    def test_processor_has_four_influencers(self) -> None:
        model = make_4gp_model()
        assert model.influencers["P"] == frozenset({"G1", "G2", "G3", "G4"})

    def test_self_influenced_by_processor(self) -> None:
        model = make_4gp_model()
        assert model.influencers["self"] == frozenset({"P"})


class TestFourGPTranslations:
    def test_each_generator_maps_to_correct_job(self) -> None:
        model = make_4gp_model()
        for i in range(1, 5):
            z = model.translations[(f"G{i}", "P")]
            result = z(OUTPUT_VALUE)
            assert result == Interval.closed(i, i)

    def test_processor_output_identity(self) -> None:
        model = make_4gp_model()
        z = model.translations[("P", "self")]
        val = Interval.closed(1, 1)
        assert z(val) == val


class TestFourGPSelect:
    def test_select_picks_first_alphabetically(self) -> None:
        model = make_4gp_model()
        candidates = frozenset({"G1", "G2", "G3", "G4"})
        assert model.select(candidates) == "G1"

    def test_select_with_subset(self) -> None:
        model = make_4gp_model()
        assert model.select(frozenset({"G3", "G4"})) == "G3"

    def test_select_single(self) -> None:
        model = make_4gp_model()
        assert model.select(frozenset({"P"})) == "P"
