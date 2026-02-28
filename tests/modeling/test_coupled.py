"""Tests for CoupledModel data structure and validation."""

from __future__ import annotations

import pytest

from cadpya.basic_models.generator import ZERO_STATE, Generator
from cadpya.basic_models.processor import ZERO_TOCJ, Processor, ProcessorState
from cadpya.modeling.component import ComponentSpec
from cadpya.modeling.coupled import CoupledModel
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def _select_first(candidates: frozenset[str]) -> str:
    return sorted(candidates)[0]


def _identity(y: Interval) -> Interval:  # type: ignore[type-arg]
    return y


def _make_job(job_id: int):
    def translate(y: Interval) -> Interval:  # type: ignore[type-arg]
        return Interval.closed(job_id, job_id)

    return translate


def _gen_spec() -> ComponentSpec:
    return ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME)


def _proc_spec() -> ComponentSpec:
    empty = ProcessorState(tocj=ZERO_TOCJ, qj=())
    return ComponentSpec.atomic(Processor, Interval.empty(empty), ZERO_TIME)


class TestConstruction:
    def test_minimal_coupled_model(self) -> None:
        """One component, no connections, no influencers on self."""
        model = CoupledModel(
            components={"G": _gen_spec()},
            influencers={"G": frozenset()},
            translations={},
            select=_select_first,
            zero_time=ZERO,
        )
        assert len(model.components) == 1
        assert model.zero_time == ZERO

    def test_with_ic_and_eoc(self) -> None:
        model = CoupledModel(
            components={"G": _gen_spec(), "P": _proc_spec()},
            influencers={
                "G": frozenset(),
                "P": frozenset({"G"}),
                "self": frozenset({"P"}),
            },
            translations={
                ("G", "P"): _make_job(1),
                ("P", "self"): _identity,
            },
            select=_select_first,
            zero_time=ZERO,
        )
        assert len(model.components) == 2
        assert model.influencers["P"] == frozenset({"G"})

    def test_frozen(self) -> None:
        model = CoupledModel(
            components={"G": _gen_spec()},
            influencers={"G": frozenset()},
            translations={},
            select=_select_first,
            zero_time=ZERO,
        )
        with pytest.raises(AttributeError):
            model.zero_time = ZERO  # type: ignore[misc]

    def test_fields_accessible(self) -> None:
        model = CoupledModel(
            components={"G": _gen_spec(), "P": _proc_spec()},
            influencers={
                "G": frozenset(),
                "P": frozenset({"G"}),
                "self": frozenset({"P"}),
            },
            translations={
                ("G", "P"): _make_job(1),
                ("P", "self"): _identity,
            },
            select=_select_first,
            zero_time=ZERO,
        )
        assert "G" in model.components
        assert "P" in model.components
        assert ("G", "P") in model.translations
        assert ("P", "self") in model.translations
        assert model.select is _select_first


class TestValidationRule1EmptyComponents:
    def test_empty_components_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one component"):
            CoupledModel(
                components={},
                influencers={},
                translations={},
                select=_select_first,
                zero_time=ZERO,
            )


class TestValidationRule2InfluencerReferences:
    def test_unknown_influencer_destination(self) -> None:
        with pytest.raises(ValueError, match="'X' is an influencer destination"):
            CoupledModel(
                components={"G": _gen_spec()},
                influencers={"G": frozenset(), "X": frozenset()},
                translations={},
                select=_select_first,
                zero_time=ZERO,
            )

    def test_unknown_influencer_source(self) -> None:
        with pytest.raises(ValueError, match="'X' is listed as an influencer of 'G'"):
            CoupledModel(
                components={"G": _gen_spec()},
                influencers={"G": frozenset({"X"})},
                translations={("X", "G"): _identity},
                select=_select_first,
                zero_time=ZERO,
            )


class TestValidationRule3AllComponentsHaveInfluencers:
    def test_missing_influencer_entry(self) -> None:
        with pytest.raises(ValueError, match="'P' has no influencer entry"):
            CoupledModel(
                components={"G": _gen_spec(), "P": _proc_spec()},
                influencers={"G": frozenset()},
                translations={},
                select=_select_first,
                zero_time=ZERO,
            )


class TestValidationRule4TranslationEndpoints:
    def test_unknown_translation_source(self) -> None:
        with pytest.raises(ValueError, match="translation source 'X'"):
            CoupledModel(
                components={"G": _gen_spec()},
                influencers={"G": frozenset()},
                translations={("X", "G"): _identity},
                select=_select_first,
                zero_time=ZERO,
            )

    def test_unknown_translation_destination(self) -> None:
        with pytest.raises(ValueError, match="translation destination 'X'"):
            CoupledModel(
                components={"G": _gen_spec()},
                influencers={"G": frozenset()},
                translations={("G", "X"): _identity},
                select=_select_first,
                zero_time=ZERO,
            )


class TestValidationRule5TranslationsMatchInfluencers:
    def test_translation_without_influencer(self) -> None:
        with pytest.raises(
            ValueError,
            match="'G' is not listed as an influencer of 'P'",
        ):
            CoupledModel(
                components={"G": _gen_spec(), "P": _proc_spec()},
                influencers={"G": frozenset(), "P": frozenset()},
                translations={("G", "P"): _make_job(1)},
                select=_select_first,
                zero_time=ZERO,
            )


class TestValidationRule6InfluencersHaveTranslations:
    def test_influencer_without_translation(self) -> None:
        with pytest.raises(
            ValueError,
            match="'G' is listed as an influencer of 'P', but no translation",
        ):
            CoupledModel(
                components={"G": _gen_spec(), "P": _proc_spec()},
                influencers={"G": frozenset(), "P": frozenset({"G"})},
                translations={},
                select=_select_first,
                zero_time=ZERO,
            )


class TestValidationRule7SelfReserved:
    def test_self_as_component_name(self) -> None:
        with pytest.raises(ValueError, match="'self' is a reserved name"):
            CoupledModel(
                components={"self": _gen_spec()},
                influencers={"self": frozenset()},
                translations={},
                select=_select_first,
                zero_time=ZERO,
            )
