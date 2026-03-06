"""Example: 2 Generators + 1 Counter.

A fast generator sends ADD events and a slow generator sends RESET events.
The counter accumulates ADDs and outputs the count on RESET.

    FastGen  --[ADD]----> Counter --[identity]--> (output)
    SlowGen  --[RESET]--/
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from cadpya.basic_models.counter import Counter, CounterState, InputEvent, Phase
from cadpya.basic_models.generator import ZERO_STATE, make_generator_factory
from cadpya.engine.root_coordinator import RootCoordinator
from cadpya.modeling.component import ComponentSpec
from cadpya.modeling.coupled import CoupledModel
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

from log_utils import write_jsonl

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)

# Fast generator: period [0.090, 0.110]
FastGen = make_generator_factory(
    period=Interval.closed(Decimal(3, "0.090"), Decimal(3, "0.110")),
    output_value=Interval.closed(Decimal(3, "1.000"), Decimal(3, "1.000")),
)

# Slow generator: period [0.950, 1.050]
SlowGen = make_generator_factory(
    period=Interval.closed(Decimal(3, "0.950"), Decimal(3, "1.050")),
    output_value=Interval.closed(Decimal(3, "1.000"), Decimal(3, "1.000")),
)


def _z_fast_counter(y: Interval[Any]) -> Interval[Any]:
    """Z: FastGen output → InputEvent.ADD."""
    return Interval.closed(InputEvent.ADD, InputEvent.ADD)


def _z_slow_counter(y: Interval[Any]) -> Interval[Any]:
    """Z: SlowGen output → InputEvent.RESET."""
    return Interval.closed(InputEvent.RESET, InputEvent.RESET)


def _z_counter_self(y: Interval[Any]) -> Interval[Any]:
    """Z: Counter output → self (identity)."""
    return y


def _select_alphabetical(candidates: frozenset[str]) -> str:
    return sorted(candidates)[0]


def make_counter_model() -> CoupledModel[Decimal]:
    """Build the 2G+Counter coupled model."""
    initial_counter = CounterState(Phase.PASSIVE, 0)
    return CoupledModel(
        components={
            "FastGen": ComponentSpec.atomic(FastGen, ZERO_STATE, ZERO_TIME),
            "SlowGen": ComponentSpec.atomic(SlowGen, ZERO_STATE, ZERO_TIME),
            "Counter": ComponentSpec.atomic(
                Counter,
                Interval.closed(initial_counter, initial_counter),
                ZERO_TIME,
            ),
        },
        influencers={
            "FastGen": frozenset(),
            "SlowGen": frozenset(),
            "Counter": frozenset({"FastGen", "SlowGen"}),
            "self": frozenset({"Counter"}),
        },
        translations={
            ("FastGen", "Counter"): _z_fast_counter,
            ("SlowGen", "Counter"): _z_slow_counter,
            ("Counter", "self"): _z_counter_self,
        },
        select=_select_alphabetical,
        zero_time=ZERO,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="2 Generators + Counter simulation")
    parser.add_argument("--max-steps", type=int, default=200, help="Max total steps (default: 200)")
    parser.add_argument("--max-branches", type=int, default=500, help="Max active branches (default: 500)")
    parser.add_argument("--progress", type=int, default=0, metavar="N", help="Print progress every N steps")
    args = parser.parse_args()

    start = time.monotonic()

    def _on_progress(steps: int) -> None:
        print(f"  progress: {steps} steps | {time.monotonic() - start:.1f}s elapsed", flush=True)

    model = make_counter_model()
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

    write_jsonl(log, Path(__file__).parent / "logs" / "counter_log.jsonl")


if __name__ == "__main__":
    main()
