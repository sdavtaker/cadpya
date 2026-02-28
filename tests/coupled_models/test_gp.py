"""Tests for Example 1: Generator-Processor coupled model (GP).

The simplest coupled model: 1 Generator feeding 1 Processor.

    G --[Z_{G,P}]--> P --[Z_{P,self}]--> (output)
"""

from __future__ import annotations

from cadpya.basic_models.generator import OUTPUT_VALUE, ZERO_STATE, Generator
from cadpya.basic_models.processor import ZERO_TOCJ, Processor, ProcessorState
from cadpya.modeling.component import ComponentSpec
from cadpya.modeling.coupled import CoupledModel
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def _select_alphabetical(candidates: frozenset[str]) -> str:
    return sorted(candidates)[0]


def _z_g_p(y: Interval) -> Interval:  # type: ignore[type-arg]
    """Z_{G,P}: Generator output → Processor input (job 1)."""
    return Interval.closed(1, 1)


def _z_p_self(y: Interval) -> Interval:  # type: ignore[type-arg]
    """Z_{P,self}: Processor output → coupled model output (identity)."""
    return y


def make_gp_model() -> CoupledModel[Decimal]:
    """Build the GP coupled model."""
    empty_proc = ProcessorState(tocj=ZERO_TOCJ, qj=())
    return CoupledModel(
        components={
            "G": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "P": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
        },
        influencers={
            "G": frozenset(),
            "P": frozenset({"G"}),
            "self": frozenset({"P"}),
        },
        translations={
            ("G", "P"): _z_g_p,
            ("P", "self"): _z_p_self,
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


class TestGPConstruction:
    def test_validates_successfully(self) -> None:
        model = make_gp_model()
        assert len(model.components) == 2

    def test_component_names(self) -> None:
        model = make_gp_model()
        assert set(model.components.keys()) == {"G", "P"}

    def test_generator_spec_is_atomic(self) -> None:
        model = make_gp_model()
        assert model.components["G"].is_atomic
        assert model.components["G"].model_factory is Generator

    def test_processor_spec_is_atomic(self) -> None:
        model = make_gp_model()
        assert model.components["P"].is_atomic
        assert model.components["P"].model_factory is Processor


class TestGPInfluencers:
    def test_generator_has_no_influencers(self) -> None:
        model = make_gp_model()
        assert model.influencers["G"] == frozenset()

    def test_processor_influenced_by_generator(self) -> None:
        model = make_gp_model()
        assert model.influencers["P"] == frozenset({"G"})

    def test_self_influenced_by_processor(self) -> None:
        model = make_gp_model()
        assert model.influencers["self"] == frozenset({"P"})


class TestGPTranslations:
    def test_z_g_p_produces_job_id(self) -> None:
        model = make_gp_model()
        z = model.translations[("G", "P")]
        result = z(OUTPUT_VALUE)
        assert result == Interval.closed(1, 1)

    def test_z_p_self_is_identity(self) -> None:
        model = make_gp_model()
        z = model.translations[("P", "self")]
        job_out = Interval.closed(1, 1)
        assert z(job_out) == job_out
