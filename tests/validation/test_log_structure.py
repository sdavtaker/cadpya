"""Validate log structure: parent references, acyclicity, step ordering."""

from __future__ import annotations

from cadpya.engine.root_coordinator import RootCoordinator
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval
from tests.coupled_models.test_4gp import make_4gp_model

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def _run_4gp(max_steps: int = 50):
    rc: RootCoordinator[Decimal] = RootCoordinator()
    return rc.simulate(make_4gp_model(), ZERO_TIME, max_steps=max_steps)


class TestLogStructure:
    def test_parent_branch_refs_valid(self) -> None:
        """Every parent_branch references a branch that appears in the log."""
        log = _run_4gp()
        branch_ids = {e.branch for e in log}
        # Root branch "0" might not appear as an entry branch but is valid
        branch_ids.add("0")

        for entry in log:
            if entry.parent_branch is not None:
                assert entry.parent_branch in branch_ids, (
                    f"Branch {entry.branch} references unknown parent {entry.parent_branch}"
                )

    def test_branch_tree_acyclic(self) -> None:
        """Walking parent_branch chains always reaches root without cycles."""
        log = _run_4gp()
        parent_map: dict[str, str | None] = {}
        for entry in log:
            parent_map[entry.branch] = entry.parent_branch

        for branch_id in parent_map:
            visited: set[str] = set()
            current: str | None = branch_id
            while current is not None:
                assert current not in visited, f"Cycle detected at {current}"
                visited.add(current)
                current = parent_map.get(current)

    def test_step_numbers_non_decreasing(self) -> None:
        """Within entries of the same branch, step numbers don't decrease."""
        log = _run_4gp()
        by_branch: dict[str, list[int]] = {}
        for entry in log:
            by_branch.setdefault(entry.branch, []).append(entry.step)

        for branch_id, steps in by_branch.items():
            for i in range(1, len(steps)):
                assert steps[i] >= steps[i - 1], (
                    f"Branch {branch_id}: step {steps[i]} < {steps[i - 1]}"
                )
