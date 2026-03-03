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
    parent_branch: str | None
    step: int
    time: str


@dataclass
class _SimulationBranch:
    """One branch of the BFS simulation tree."""

    branch_id: str
    coordinator: Coordinator[Any, Any]
    parent_branch_id: str | None
    step: int


class RootCoordinator[T]:
    """IA-DEVS Root Coordinator with BFS branching (Algorithm 4)."""

    def simulate(
        self,
        coupled_model: CoupledModel[T],
        t: Interval[T],
        *,
        max_steps: int = 10000,
        max_branches: int = 1000,
    ) -> list[LogEntry]:
        """Run BFS simulation, returning structured log.

        Args:
            coupled_model: the coupled model to simulate
            t: initial simulation time interval
            max_steps: total steps across all branches; simulation stops
                gracefully when reached and returns the log collected so far.
            max_branches: maximum active branches in queue; raises
                SimulationLimitError if exceeded (indicates exponential blowup).

        Returns:
            List of LogEntry recording each step.

        Raises:
            SimulationLimitError: if max_branches is exceeded.
        """
        coord: Coordinator[T, Any] = Coordinator(coupled_model, coupled_model.zero_time)
        coord.init(t)

        queue: deque[_SimulationBranch] = deque()
        queue.append(_SimulationBranch("0", coord, None, 0))

        log: list[LogEntry] = []
        total_steps = 0

        while queue:
            if total_steps >= max_steps:
                break

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
                            parent_branch=branch.parent_branch_id,
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
                    msg = f"Simulation exceeded max_branches limit ({max_branches})"
                    raise SimulationLimitError(msg)

                for i, action in enumerate(actions):
                    if total_steps >= max_steps:
                        break

                    clone = copy.deepcopy(branch.coordinator)
                    component_output, _ = clone.execute_branch(action)
                    total_steps += 1

                    new_id = f"{branch.branch_id}.{i}"

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
                            parent_branch=branch.branch_id,
                            time=str(action.limit),
                            component=action.engine_name,
                            output=str(component_output) if component_output is not None else None,
                        )
                    )

                    new_branch = _SimulationBranch(
                        branch_id=new_id,
                        coordinator=clone,
                        parent_branch_id=branch.branch_id,
                        step=branch.step + 1,
                    )

                    if clone.t_next is not None:
                        queue.append(new_branch)

        return log
