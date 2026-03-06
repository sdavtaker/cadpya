"""Example: 4 Generators + 1 Processor (4GP).

The paper's case study: four generators feed one processor.
Each generator produces periodic output with uncertainty, and the
processor handles jobs from a FIFO queue.

    G1 --[job=1]--> P --[identity]--> (output)
    G2 --[job=2]--/
    G3 --[job=3]--/
    G4 --[job=4]--/
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from cadpya.basic_models.generator import ZERO_STATE, Generator
from cadpya.basic_models.processor import ZERO_TOCJ, Processor, ProcessorState
from cadpya.engine.root_coordinator import RootCoordinator
from cadpya.modeling.component import ComponentSpec
from cadpya.modeling.coupled import CoupledModel
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

from log_utils import write_jsonl

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def _select_alphabetical(candidates: frozenset[str]) -> str:
    return sorted(candidates)[0]


def _make_z_gen_proc(job_id: int) -> Any:
    """Z_{Gi,P}: Generator output → Processor input (job_id)."""

    def translate(y: Interval[Any]) -> Interval[Any]:
        return Interval.closed(job_id, job_id)

    return translate


def _z_p_self(y: Interval[Any]) -> Interval[Any]:
    """Z_{P,self}: identity."""
    return y


def make_4gp_model() -> CoupledModel[Decimal]:
    """Build the 4GP coupled model."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description="4 Generators + Processor simulation")
    parser.add_argument("--max-steps", type=int, default=200, help="Max total steps (default: 200)")
    parser.add_argument("--max-branches", type=int, default=500, help="Max active branches (default: 500)")
    parser.add_argument("--progress", type=int, default=0, metavar="N", help="Print progress every N steps")
    args = parser.parse_args()

    start = time.monotonic()

    def _on_progress(steps: int) -> None:
        print(f"  progress: {steps} steps | {time.monotonic() - start:.1f}s elapsed", flush=True)

    model = make_4gp_model()
    rc: RootCoordinator[Decimal] = RootCoordinator()
    log = rc.simulate(
        model, ZERO_TIME,
        max_steps=args.max_steps,
        max_branches=args.max_branches,
        progress_interval=args.progress,
        on_progress=_on_progress if args.progress > 0 else None,
    )

    print(f"Simulation produced {len(log)} log entries")
    for entry in log[:10]:
        print(f"  [{entry.branch}] step={entry.step} t={entry.time} "
              f"component={entry.component} output={entry.output}")
    if len(log) > 10:
        print(f"  ... and {len(log) - 10} more")

    write_jsonl(log, Path(__file__).parent / "logs" / "4gp_log.jsonl")


if __name__ == "__main__":
    main()
