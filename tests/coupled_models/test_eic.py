"""Tests for Example 4: EIC (External Input Coupling) coupled model.

Exercises External Input Coupling (EIC) which none of the other examples cover.

Two coupled models connected at the top level:

Top-level:
    Generators = CoupledModel(G1, G2) --[Z]--> GPP = CoupledModel(G3, G4, P) --> (output)

Generators (EOC only):
    G1 --[Z_{G1,self}]--> (output)    [job 1]
    G2 --[Z_{G2,self}]--> (output)    [job 2]

GPP (has EIC + IC + EOC):
    (input) --[Z_{self,P}]--> P       [EIC: external input routed to P]
    G3 --[Z_{G3,P}]---------> P       [IC: job 3]
    G4 --[Z_{G4,P}]---------> P       [IC: job 4]
    P  --[Z_{P,self}]-------> (output) [EOC]

Semantically equivalent to flat 4GP: 4 generators all feed 1 processor.
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


def _make_z_job(job_id: int) -> Callable[[Interval[Any]], Interval[Any]]:
    """Create Z function that maps any output to a job ID interval."""

    def translate(y: Interval) -> Interval:  # type: ignore[type-arg]
        return Interval.closed(job_id, job_id)

    return translate


def _identity(y: Interval) -> Interval:  # type: ignore[type-arg]
    return y


def make_generators_model() -> CoupledModel[Decimal]:
    """Sub-coupled model: G1 and G2 with EOC only."""
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


def make_gpp_model() -> CoupledModel[Decimal]:
    """Sub-coupled model: G3, G4, P with EIC + IC + EOC.

    The key feature: "self" is an influencer of "P" (EIC).
    External input arrives via Z_{self,P} and is routed to P.
    """
    empty_proc = ProcessorState(tocj=ZERO_TOCJ, qj=())
    return CoupledModel(
        components={
            "G3": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G4": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "P": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
        },
        influencers={
            "G3": frozenset(),
            "G4": frozenset(),
            "P": frozenset({"G3", "G4", "self"}),
            "self": frozenset({"P"}),
        },
        translations={
            ("self", "P"): _identity,
            ("G3", "P"): _make_z_job(3),
            ("G4", "P"): _make_z_job(4),
            ("P", "self"): _identity,
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


def make_eic_top_model() -> CoupledModel[Decimal]:
    """Top-level: Generators feeds GPP, GPP outputs externally."""
    return CoupledModel(
        components={
            "Generators": ComponentSpec.coupled(make_generators_model()),
            "GPP": ComponentSpec.coupled(make_gpp_model()),
        },
        influencers={
            "Generators": frozenset(),
            "GPP": frozenset({"Generators"}),
            "self": frozenset({"GPP"}),
        },
        translations={
            ("Generators", "GPP"): _identity,
            ("GPP", "self"): _identity,
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


class TestGeneratorsSubModel:
    def test_validates(self) -> None:
        model = make_generators_model()
        assert len(model.components) == 2

    def test_eoc_sources(self) -> None:
        model = make_generators_model()
        assert model.influencers["self"] == frozenset({"G1", "G2"})


class TestGPPSubModel:
    def test_validates(self) -> None:
        model = make_gpp_model()
        assert len(model.components) == 3

    def test_has_eic(self) -> None:
        """P is influenced by 'self' — this is the EIC."""
        model = make_gpp_model()
        assert "self" in model.influencers["P"]

    def test_eic_translation_exists(self) -> None:
        model = make_gpp_model()
        assert ("self", "P") in model.translations

    def test_eic_translation_is_identity(self) -> None:
        model = make_gpp_model()
        z = model.translations[("self", "P")]
        job_input = Interval.closed(1, 1)
        assert z(job_input) == job_input

    def test_processor_has_three_influencers(self) -> None:
        """P is influenced by G3, G4, and self (EIC)."""
        model = make_gpp_model()
        assert model.influencers["P"] == frozenset({"G3", "G4", "self"})

    def test_ic_translations(self) -> None:
        model = make_gpp_model()
        assert model.translations[("G3", "P")](OUTPUT_VALUE) == Interval.closed(3, 3)
        assert model.translations[("G4", "P")](OUTPUT_VALUE) == Interval.closed(4, 4)

    def test_eoc(self) -> None:
        model = make_gpp_model()
        assert model.influencers["self"] == frozenset({"P"})


class TestEICTopLevel:
    def test_validates(self) -> None:
        model = make_eic_top_model()
        assert len(model.components) == 2

    def test_component_names(self) -> None:
        model = make_eic_top_model()
        assert set(model.components.keys()) == {"Generators", "GPP"}

    def test_both_are_coupled(self) -> None:
        model = make_eic_top_model()
        assert model.components["Generators"].is_coupled
        assert model.components["GPP"].is_coupled

    def test_gpp_influenced_by_generators(self) -> None:
        model = make_eic_top_model()
        assert model.influencers["GPP"] == frozenset({"Generators"})

    def test_generators_no_influencers(self) -> None:
        model = make_eic_top_model()
        assert model.influencers["Generators"] == frozenset()

    def test_eoc_from_gpp(self) -> None:
        model = make_eic_top_model()
        assert model.influencers["self"] == frozenset({"GPP"})

    def test_nested_gpp_has_eic(self) -> None:
        """Verify the nested GPP model retains its EIC structure."""
        model = make_eic_top_model()
        gpp = model.components["GPP"].coupled_model
        assert gpp is not None
        assert "self" in gpp.influencers["P"]
