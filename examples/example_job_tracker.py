"""Example: 4 Generators + 1 Processor + 4 Accumulators (Job Tracker).

Extends the 4GP model with per-job accumulators that count how many
times each job ID was processed.

    G1 --[job=1]--> P --[indicator]--> S1 --[tagged]--> (output)
    G2 --[job=2]--/    `-[indicator]--> S2 --[tagged]-->
    G3 --[job=3]--/    `-[indicator]--> S3 --[tagged]-->
    G4 --[job=4]--/    `-[indicator]--> S4 --[tagged]-->

The Z function from P to Si uses indicator semantics:
- If P outputs exactly job i: Si gets [1, 1]
- If P output interval contains i but isn't exact: Si gets [0, 1]
- If P output interval doesn't contain i: Si gets [0, 0]
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path
from typing import Any

from cadpya.basic_models.accumulator import Accumulator, AccumulatorState, Phase
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


@total_ordering
@dataclass(frozen=True, slots=True)
class TaggedCount:
    """Tagged accumulator output: ``j1:5`` means job 1 processed 5 times."""

    count: int
    tag: str

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, TaggedCount):
            return NotImplemented
        if self.tag != other.tag:
            return self.tag < other.tag
        return self.count < other.count

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TaggedCount):
            return NotImplemented
        return self.tag == other.tag and self.count == other.count

    def __hash__(self) -> int:
        return hash((self.tag, self.count))

    def __str__(self) -> str:
        return f"{self.tag}:{self.count}"


def _select_alphabetical(candidates: frozenset[str]) -> str:
    return sorted(candidates)[0]


def _make_z_gen_proc(job_id: int) -> Any:
    """Z_{Gi,P}: Generator output → Processor input (job_id)."""

    def translate(y: Interval[Any]) -> Interval[Any]:
        return Interval.closed(job_id, job_id)

    return translate


def _make_z_proc_accum(job_id: int) -> Any:
    """Z_{P,Si}: Processor output → Accumulator input (indicator).

    Uses interval indicator semantics:
    - exact match (interval is [i, i]): [1, 1]
    - possible match (i within interval): [0, 1]
    - no match: [0, 0]
    """

    def translate(y: Interval[Any]) -> Interval[Any]:
        contains = y.lower <= job_id <= y.upper
        exact = y.lower == y.upper == job_id
        lo = 1 if exact else 0
        hi = 1 if contains else 0
        return Interval.closed(lo, hi)

    return translate


def _make_z_accum_self(tag: str) -> Any:
    """Z_{Si,self}: Accumulator output → tagged output."""

    def translate(y: Interval[Any]) -> Interval[Any]:
        return Interval.closed(
            TaggedCount(tag=tag, count=y.lower),
            TaggedCount(tag=tag, count=y.upper),
        )

    return translate


def make_job_tracker_model() -> CoupledModel[Decimal]:
    """Build the 4G+P+4S job tracker coupled model."""
    empty_proc = ProcessorState(tocj=ZERO_TOCJ, qj=())
    passive_accum = AccumulatorState(Phase.PASSIVE, 0)
    initial_accum = Interval.closed(passive_accum, passive_accum)

    return CoupledModel(
        components={
            "G1": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G2": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G3": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "G4": ComponentSpec.atomic(Generator, ZERO_STATE, ZERO_TIME),
            "P": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
            "S1": ComponentSpec.atomic(Accumulator, initial_accum, ZERO_TIME),
            "S2": ComponentSpec.atomic(Accumulator, initial_accum, ZERO_TIME),
            "S3": ComponentSpec.atomic(Accumulator, initial_accum, ZERO_TIME),
            "S4": ComponentSpec.atomic(Accumulator, initial_accum, ZERO_TIME),
        },
        influencers={
            "G1": frozenset(),
            "G2": frozenset(),
            "G3": frozenset(),
            "G4": frozenset(),
            "P": frozenset({"G1", "G2", "G3", "G4"}),
            "S1": frozenset({"P"}),
            "S2": frozenset({"P"}),
            "S3": frozenset({"P"}),
            "S4": frozenset({"P"}),
            "self": frozenset({"S1", "S2", "S3", "S4"}),
        },
        translations={
            ("G1", "P"): _make_z_gen_proc(1),
            ("G2", "P"): _make_z_gen_proc(2),
            ("G3", "P"): _make_z_gen_proc(3),
            ("G4", "P"): _make_z_gen_proc(4),
            ("P", "S1"): _make_z_proc_accum(1),
            ("P", "S2"): _make_z_proc_accum(2),
            ("P", "S3"): _make_z_proc_accum(3),
            ("P", "S4"): _make_z_proc_accum(4),
            ("S1", "self"): _make_z_accum_self("j1"),
            ("S2", "self"): _make_z_accum_self("j2"),
            ("S3", "self"): _make_z_accum_self("j3"),
            ("S4", "self"): _make_z_accum_self("j4"),
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="4 Generators + Processor + 4 Accumulators simulation")
    parser.add_argument("--max-steps", type=int, default=200, help="Max total steps (default: 200)")
    parser.add_argument("--max-branches", type=int, default=500, help="Max active branches (default: 500)")
    parser.add_argument("--progress", type=int, default=0, metavar="N", help="Print progress every N steps")
    args = parser.parse_args()

    start = time.monotonic()

    def _on_progress(steps: int) -> None:
        print(f"  progress: {steps} steps | {time.monotonic() - start:.1f}s elapsed", flush=True)

    model = make_job_tracker_model()
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

    write_jsonl(log, Path(__file__).parent / "logs" / "job_tracker_log.jsonl")


if __name__ == "__main__":
    main()
