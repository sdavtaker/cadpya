"""Validate 4GP branching behavior via RootCoordinator BFS simulation."""

from __future__ import annotations

from cadpya.engine.root_coordinator import RootCoordinator
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval
from tests.coupled_models.test_4gp import make_4gp_model

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


class TestFirstWave:
    def test_4_branches_at_step_0(self) -> None:
        """All 4 generators are simultaneously imminent → 4 branches."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=4)

        step0 = [e for e in log if e.step == 0]
        assert len(step0) == 4
        assert {e.component for e in step0} == {"G1", "G2", "G3", "G4"}

    def test_12_branches_at_step_1(self) -> None:
        """Each of the 4 step-0 branches has 3 remaining generators → 12."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=20)

        step1 = [e for e in log if e.step == 1]
        assert len(step1) == 12

    def test_24_branches_at_step_2(self) -> None:
        """12 branches x 2 remaining generators = 24."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=50)

        step2 = [e for e in log if e.step == 2]
        assert len(step2) == 24

    def test_24_branches_at_step_3(self) -> None:
        """24 branches x 1 remaining generator = 24 (last generator fires)."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=120)

        step3 = [e for e in log if e.step == 3]
        assert len(step3) == 24


class TestAllPermutations:
    def test_24_distinct_generator_orderings(self) -> None:
        """After 4 generator steps, all 4! = 24 permutations are represented."""
        model = make_4gp_model()
        rc: RootCoordinator[Decimal] = RootCoordinator()
        log = rc.simulate(model, ZERO_TIME, max_steps=120)

        # Build branch lineages for steps 0-3
        orderings: set[tuple[str, ...]] = set()
        branches_at_3 = {e.branch for e in log if e.step == 3}

        for branch_id in branches_at_3:
            # Collect all entries in this branch's lineage
            lineage: list[str] = []
            current = branch_id
            while current:
                entries = [e for e in log if e.branch == current]
                for e in entries:
                    lineage.append(e.component)
                # Find parent
                parents = [e.parent_branch for e in log if e.branch == current]
                current = parents[0] if parents else None

            # Lineage is in reverse order (deepest first)
            lineage.reverse()
            orderings.add(tuple(lineage))

        assert len(orderings) == 24
