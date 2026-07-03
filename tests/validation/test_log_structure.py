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
        """Every parent_branches entry references a branch that appears in the log."""
        log = _run_4gp()
        branch_ids = {e.branch for e in log}
        # Root branch "0" may not appear as a log entry if branching happens
        # immediately at step 0 (before any root-branch component fires).
        branch_ids.add("0")

        for entry in log:
            for pid in entry.parent_branches:
                assert pid in branch_ids, f"Branch {entry.branch} references unknown parent {pid}"

    def test_branch_dag_acyclic(self) -> None:
        """The parent-branch DAG has no cycles."""
        log = _run_4gp()
        # Union parent_branches across ALL entries for each branch so that
        # edges added by later dedup merges are not missed.
        parents: dict[str, set[str]] = {}
        for entry in log:
            parents.setdefault(entry.branch, set()).update(entry.parent_branches)

        # BFS from each node; reaching the starting node again means a cycle.
        for start in parents:
            visited: set[str] = set()
            frontier = list(parents.get(start, set()))
            while frontier:
                node = frontier.pop()
                assert node != start, f"Cycle detected: {start} is its own ancestor"
                if node not in visited:
                    visited.add(node)
                    frontier.extend(parents.get(node, set()))

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

    def test_kind_field_valid_values(self) -> None:
        """Every log entry has a valid kind."""
        log = _run_4gp()
        valid_kinds = {"atomic", "coupled", "skip"}
        for entry in log:
            assert entry.kind in valid_kinds, (
                f"Branch {entry.branch} has invalid kind '{entry.kind}'"
            )

    def test_skip_entries_have_empty_component_and_no_output(self) -> None:
        """Skip entries must have component='' and output=None."""
        log = _run_4gp()
        for entry in log:
            if entry.kind == "skip":
                assert entry.component == "", (
                    f"skip entry {entry.branch} has non-empty component '{entry.component}'"
                )
                assert entry.output is None, (
                    f"skip entry {entry.branch} has unexpected output '{entry.output}'"
                )

    def test_non_skip_entries_have_non_empty_component(self) -> None:
        """Atomic and coupled entries must have a non-empty component name."""
        log = _run_4gp()
        for entry in log:
            if entry.kind not in ("skip",):
                assert entry.component != "", (
                    f"Non-skip entry {entry.branch} (kind={entry.kind}) has empty component"
                )

    def test_parent_branches_is_tuple(self) -> None:
        """parent_branches must always be a tuple (immutable sequence), never None."""
        log = _run_4gp()
        for entry in log:
            assert isinstance(entry.parent_branches, tuple), (
                f"Branch {entry.branch}: parent_branches is {type(entry.parent_branches)}"
            )
