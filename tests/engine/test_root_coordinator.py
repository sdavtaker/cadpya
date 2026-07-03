"""Tests for the IA-DEVS Root Coordinator (Algorithm 4) with BFS branching."""

from __future__ import annotations

import pytest

from cadpya.basic_models.generator import OUTPUT_VALUE
from cadpya.engine.root_coordinator import RootCoordinator, SimulationLimitError
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval
from tests.coupled_models.test_4gp import make_4gp_model
from tests.coupled_models.test_eic import make_eic_top_model
from tests.coupled_models.test_gp import make_gp_model
from tests.coupled_models.test_hierarchical import make_hierarchical_model

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def d(s: str) -> Decimal:
    return Decimal(3, s)


class TestGPSimulation:
    """GP model: no branching, simple G→P→output flow."""

    def test_gp_produces_log(self) -> None:
        """GP should produce log entries within step limit."""
        model = make_gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=10)
        assert len(log) > 0

    def test_gp_first_step_is_generator(self) -> None:
        model = make_gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=10)
        assert log[0].component == "G"
        assert log[0].time == str(Interval.closed(d("0.997"), d("1.005")))

    def test_gp_second_step_is_processor(self) -> None:
        model = make_gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=10)
        assert log[1].component == "P"
        assert log[1].output is not None

    def test_gp_processor_outputs_job_1(self) -> None:
        model = make_gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=10)
        p_entries = [e for e in log if e.component == "P"]
        assert len(p_entries) >= 1
        assert p_entries[0].output == "[1, 1]"

    def test_gp_no_branching(self) -> None:
        """GP has only one imminent at a time → no branching."""
        model = make_gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=10)
        assert all(e.branch == "0" for e in log)

    def test_gp_respects_max_steps(self) -> None:
        """Simulation stops at max_steps and returns partial log."""
        model = make_gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=4)
        assert len(log) == 4


class TestFourGPSimulation:
    """4GP model: branching when 4 generators are simultaneously imminent."""

    def test_4gp_first_wave_branches(self) -> None:
        """First step: all 4 generators are imminent → 4 branches."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=4)
        first_step = [e for e in log if e.step == 0]
        assert len(first_step) == 4
        components = {e.component for e in first_step}
        assert components == {"G1", "G2", "G3", "G4"}

    def test_4gp_all_first_branches_have_parent(self) -> None:
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=4)
        first_step = [e for e in log if e.step == 0]
        assert all(e.parent_branches == ("0",) for e in first_step)

    def test_4gp_second_wave_more_branches(self) -> None:
        """After first 4 branches, each has 3 remaining generators → more branching."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=50)
        step_1_entries = [e for e in log if e.step == 1]
        assert len(step_1_entries) > 0

    def test_4gp_generator_output_is_output_value(self) -> None:
        """Generator output is logged even though it routes via IC (not EOC)."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=4)
        gen_entries = [e for e in log if e.component.startswith("G")]
        assert all(e.output == str(OUTPUT_VALUE) for e in gen_entries)

    def test_4gp_processor_eventually_fires(self) -> None:
        """After all 4 generators fire in a branch, P should fire."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=200)
        p_entries = [e for e in log if e.component == "P"]
        assert len(p_entries) > 0


class TestHierarchicalSimulation:
    """Hierarchical model with nested sub-coupled models."""

    def test_hierarchical_runs(self) -> None:
        model = make_hierarchical_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=10)
        assert len(log) > 0

    def test_hierarchical_first_step_is_sub_coordinators(self) -> None:
        """Left and Right sub-models contain generators that fire first."""
        model = make_hierarchical_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=4)
        first_step = [e for e in log if e.step == 0]
        components = {e.component for e in first_step}
        assert components == {"Left", "Right"}


class TestEICSimulation:
    """EIC model: external input routing through sub-Coordinator."""

    def test_eic_runs(self) -> None:
        model = make_eic_top_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=10)
        assert len(log) > 0

    def test_eic_first_step_is_generators_and_gpp(self) -> None:
        """Both Generators and GPP sub-models have imminent generators."""
        model = make_eic_top_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=4)
        first_step = [e for e in log if e.step == 0]
        components = {e.component for e in first_step}
        assert components == {"Generators", "GPP"}


class TestSafetyLimits:
    def test_max_steps_stops_gracefully(self) -> None:
        """max_steps causes graceful stop, not exception."""
        model = make_gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=3)
        assert len(log) <= 3

    def test_max_branches_raises(self) -> None:
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        with pytest.raises(SimulationLimitError, match="max_branches"):
            rc.simulate(model, ZERO_TIME, max_steps=10000, max_branches=2)


class TestParentBranches:
    def test_root_branch_has_empty_parent_branches(self) -> None:
        """Entries on the root branch (no branching) have empty parent_branches."""
        model = make_gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=5)
        for entry in log:
            assert entry.parent_branches == ()

    def test_child_branches_have_one_parent_when_dedup_off(self) -> None:
        """With dedup disabled, every child branch has exactly one parent."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator(dedup_transitions=False)
        log = rc.simulate(model, ZERO_TIME, max_steps=4)
        for entry in log:
            assert len(entry.parent_branches) == 1

    def test_dedup_off_no_multi_parent_entries(self) -> None:
        """With dedup_transitions=False, every entry has at most one parent branch."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator(dedup_transitions=False)
        log = rc.simulate(model, ZERO_TIME, max_steps=50)
        for entry in log:
            assert len(entry.parent_branches) <= 1

    def test_dedup_on_produces_same_outputs_as_dedup_off(self) -> None:
        """Dedup must not change the set of output values — only reduce branch count."""
        model = make_4gp_model()
        on_log = RootCoordinator[Decimal](dedup_transitions=True).simulate(
            model, ZERO_TIME, max_steps=200
        )
        off_log = RootCoordinator[Decimal](dedup_transitions=False).simulate(
            model, ZERO_TIME, max_steps=200
        )
        on_outputs = {e.output for e in on_log if e.output is not None}
        off_outputs = {e.output for e in off_log if e.output is not None}
        assert on_outputs == off_outputs
