"""IA-DEVS Root Coordinator with BFS branching.

Implements Algorithm 4 from "Uncertainty on Discrete-Event System
Simulation" (VWD21). Drives the top-level simulation loop with
breadth-first branching exploration.
"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cadpya.engine.coordinator import Coordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from cadpya.modeling.coupled import CoupledModel
    from cadpya.modeling.interval import Interval


class SimulationLimitError(Exception):
    """Raised when simulation exceeds safety limits."""


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One step in the simulation log."""

    branch: str
    component: str
    kind: str  # "atomic", "coupled", or "skip"
    output: str | None
    parent_branches: list[str]
    step: int
    time: str


@dataclass
class _SimulationBranch:
    """One branch of the BFS simulation tree."""

    branch_id: str
    coordinator: Coordinator[Any, Any]
    parent_branch_ids: list[str]
    step: int


class RootCoordinator[T]:
    """IA-DEVS Root Coordinator with BFS branching (Algorithm 4).

    Args:
        dedup_transitions: when True (default), branches whose coordinator
            states are structurally equal are merged before execution.
            Disable for validation runs that need the full unmerged log.
    """

    def __init__(self, *, dedup_transitions: bool = True) -> None:
        self._dedup = dedup_transitions

    def simulate(
        self,
        coupled_model: CoupledModel[T],
        t: Interval[T],
        *,
        max_steps: int = 10000,
        max_branches: int = 1000,
        progress_interval: int = 0,
        on_progress: Callable[[int], None] | None = None,
    ) -> list[LogEntry]:
        """Run BFS simulation, returning structured log.

        Args:
            coupled_model: the coupled model to simulate
            t: initial simulation time interval
            max_steps: total steps across all branches; simulation stops
                gracefully when reached and returns the log collected so far.
            max_branches: maximum active branches in queue; raises
                SimulationLimitError if exceeded (indicates exponential blowup).
            progress_interval: call on_progress every this many steps (0 = disabled).
            on_progress: callback receiving total_steps; called when progress_interval > 0.

        Returns:
            List of LogEntry recording each step.  Each entry has a
            ``parent_branches`` list: empty for the root branch, one element
            for an ordinary child branch, and two or more elements when
            dedup_transitions is True and multiple structurally-equal branches
            were merged into one (recording all contributing parent branches).

        Raises:
            SimulationLimitError: if max_branches is exceeded.
        """
        coord: Coordinator[T, Any] = Coordinator(coupled_model, coupled_model.zero_time)
        coord.init(t)

        queue: deque[_SimulationBranch] = deque()
        queue.append(_SimulationBranch("0", coord, [], 0))

        log: list[LogEntry] = []
        total_steps = 0
        last_reported = 0
        next_branch_id = 1  # monotonic counter for child branch IDs

        while queue:
            if total_steps >= max_steps:
                break

            if (
                on_progress is not None
                and progress_interval > 0
                and total_steps - last_reported >= progress_interval
            ):
                on_progress(total_steps)
                last_reported = total_steps

            # Dedup: merge queue entries structurally equal to the head into it.
            # The surviving branch accumulates all contributing parent branch IDs.
            if self._dedup and len(queue) > 1:
                head = queue[0]
                i = 1
                seen_parents: set[str] = set(head.parent_branch_ids)
                while i < len(queue):
                    other = queue[i]
                    if head.coordinator.engine_equals(other.coordinator):
                        del queue[i]
                        for pid in other.parent_branch_ids:
                            if pid not in seen_parents:
                                head.parent_branch_ids.append(pid)
                                seen_parents.add(pid)
                    else:
                        i += 1

            branch = queue.popleft()

            if branch.coordinator.t_next is None:
                continue  # Passive — discard

            t_current = branch.coordinator.t_next

            # Compute possible branches
            actions = branch.coordinator.compute_branches(t_current)

            if not actions:
                continue

            if len(actions) == 1:
                # No branching — execute in place
                action = actions[0]
                component_output, _ = branch.coordinator.execute_branch(action)
                total_steps += 1

                if action.engine_name:
                    engine = branch.coordinator.engines.get(action.engine_name)
                    kind = "coupled" if isinstance(engine, Coordinator) else "atomic"
                    log.append(
                        LogEntry(
                            step=branch.step,
                            branch=branch.branch_id,
                            kind=kind,
                            parent_branches=list(branch.parent_branch_ids),
                            time=str(action.limit),
                            component=action.engine_name,
                            output=str(component_output) if component_output is not None else None,
                        )
                    )

                branch.step += 1

                if branch.coordinator.t_next is not None:
                    queue.append(branch)
            else:
                # Branching — clone state for each branch
                if len(queue) + len(actions) > max_branches:
                    msg = (
                        f"Simulation exceeded max_branches limit ({max_branches}) "
                        f"after {total_steps} steps"
                    )
                    raise SimulationLimitError(msg)

                for action in actions:
                    if total_steps >= max_steps:
                        break

                    clone = copy.deepcopy(branch.coordinator)
                    component_output, _ = clone.execute_branch(action)
                    total_steps += 1

                    new_id = str(next_branch_id)
                    next_branch_id += 1

                    if action.engine_name:
                        engine = branch.coordinator.engines.get(action.engine_name)
                        kind = "coupled" if isinstance(engine, Coordinator) else "atomic"
                    else:
                        kind = "skip"
                    log.append(
                        LogEntry(
                            step=branch.step,
                            branch=new_id,
                            kind=kind,
                            parent_branches=[branch.branch_id],
                            time=str(action.limit),
                            component=action.engine_name,
                            output=str(component_output) if component_output is not None else None,
                        )
                    )

                    new_branch = _SimulationBranch(
                        branch_id=new_id,
                        coordinator=clone,
                        parent_branch_ids=[branch.branch_id],
                        step=branch.step + 1,
                    )

                    if clone.t_next is not None:
                        queue.append(new_branch)

        return log
