# cadpya Log Format Reference

This document describes the JSONL log format produced by `RootCoordinator.simulate()`. It is intended as a reference for the visualization project.

## Format

Newline-delimited JSON (JSONL). Each line is one JSON object representing a single simulation step.

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `branch` | `string` | Hierarchical BFS tree ID. Root branch is `"0"`, children are assigned monotonically increasing integer IDs as strings (`"1"`, `"2"`, …). |
| `component` | `string` | Name of the component that fired. Empty string `""` for skip entries. |
| `kind` | `string` | Component kind: `"atomic"` for atomic model components, `"coupled"` for nested coupled model components, or `"skip"` for skip branches (no component fires in this interval). |
| `output` | `string \| null` | External output coupling (EOC) value as an interval string, or `null` if the component's output was routed only internally (IC), not to the coupled model boundary. Always `null` for skip entries. |
| `parent_branches` | `string[]` | Parent branch IDs. Empty array `[]` for entries on the root branch `"0"`. Normally one element. Two or more elements when dedup merges structurally-equal branches: each element is one of the contributing parent branch IDs. |
| `step` | `int` | Step number within this branch lineage. Starts at 0 and increments each time the branch advances. |
| `time` | `string` | Time interval when the event occurred, formatted as an interval string (e.g. `"[0.997, 1.005]"`). May use open bounds like `"[0.810, 0.950)"`. |

## Semantics

### BFS Branch Tree

The simulator uses breadth-first search to explore uncertainty. When multiple components are simultaneously imminent with punctual (single-point) time advances, the SELECT tie-breaking function picks one — but since the true execution order is uncertain, the simulator forks: one branch per candidate ordering.

- **No branching**: When only one component is imminent or time advances are non-punctual, the simulation proceeds linearly on the same branch.
- **Branching**: When N components are simultaneously imminent with punctual limits, N child branches are created. Each branch represents a different execution ordering.

### IC vs EOC Events

- **`output: null`**: The component fired and its output was routed to other components inside the coupled model (internal coupling, IC), but nothing reached the coupled model boundary (EOC). This is the common case for generators feeding processors.
- **`output: "[1, 1]"`**: The component's output was routed to `"self"` (the coupled model's external output port) via an EOC translation function.

### Skip Branches

When a non-punctual time interval contains multiple simultaneously imminent
components, the simulator also explores the possibility that *nothing* fires in
that interval (the event could happen later). These "skip" branches are logged
with `kind: "skip"`, `component: ""`, and `output: null`.

Every branch ID that is assigned appears in the log — including skip branches —
so `parent_branches` references are always resolvable. The only exception is the
root branch `"0"` itself, which may not appear as a log entry if branching
happens before any root-level component fires.

### Passive Branches

Branches where `t_next` becomes `None` (all components are passive with no scheduled events) are silently discarded. They do not appear in the log.

### Deduplication (`parent_branches` with multiple entries)

When `dedup_transitions=True` (the default), branches whose coordinator states
are structurally equal — same `t_last`, `t_next`, and all child engine states —
are merged before execution. The surviving branch absorbs the parent branch IDs
of all merged branches, so `parent_branches` may contain two or more entries.

This represents the fact that multiple distinct simulation paths converged to the
same IA-DEVS state: they will produce identical future behaviour, so only one
execution is needed. The visualization can render fan-in edges for multi-parent entries.

With `dedup_transitions=False`, every queued branch is executed independently and
`parent_branches` always has at most one element.

## Branch DAG Reconstruction

The log forms a directed acyclic graph (DAG) — a tree when dedup is disabled,
or a DAG when branches are merged. To build a parent → children map:

```python
import json
from collections import defaultdict

children = defaultdict(set)
with open("log.jsonl") as f:
    for line in f:
        entry = json.loads(line)
        branch = entry["branch"]
        for pid in entry["parent_branches"]:
            children[pid].add(branch)
```

## Annotated Example

From the 4GP simulation (4 Generators + 1 Processor):

```jsonl
{"branch": "1", "component": "G1", "kind": "atomic", "output": null, "parent_branches": ["0"], "step": 0, "time": "[0.997, 1.005]"}
{"branch": "2", "component": "G2", "kind": "atomic", "output": null, "parent_branches": ["0"], "step": 0, "time": "[0.997, 1.005]"}
{"branch": "3", "component": "G3", "kind": "atomic", "output": null, "parent_branches": ["0"], "step": 0, "time": "[0.997, 1.005]"}
{"branch": "4", "component": "G4", "kind": "atomic", "output": null, "parent_branches": ["0"], "step": 0, "time": "[0.997, 1.005]"}
```

**Step 0**: All four generators are simultaneously imminent at time `[0.997, 1.005]`. The simulator creates 4 branches from root `"0"`, one for each generator firing first. Each entry has `parent_branches: ["0"]`.

```jsonl
{"branch": "17", "component": "P", "kind": "atomic", "output": "[1, 1]", "parent_branches": ["16"], "step": 4, "time": "[1.223, 1.255]"}
```

**Step 4** (branch `17`): The processor finishes its first job and outputs `[1, 1]` (job ID 1) via EOC. The time interval `[1.223, 1.255]` reflects accumulated uncertainty from the generator periods and processing time.

Skip branch example (from the counter simulation):

```jsonl
{"branch": "5", "component": "FastGen", "kind": "atomic", "output": null, "parent_branches": ["0"], "step": 8, "time": "[0.810, 0.950)"}
{"branch": "6", "component": "",        "kind": "skip",   "output": null, "parent_branches": ["0"], "step": 8, "time": "[0.810, 0.950)"}
{"branch": "7", "component": "FastGen", "kind": "atomic", "output": null, "parent_branches": ["6"], "step": 9, "time": "[0.950, 0.990]"}
{"branch": "8", "component": "SlowGen", "kind": "atomic", "output": null, "parent_branches": ["6"], "step": 9, "time": "[0.950, 0.990]"}
```

**Step 8** (branching): FastGen and SlowGen have overlapping but non-punctual `t_next` intervals. The limit `[0.810, 0.950)` is strictly inside FastGen's `t_next`, so a skip branch `"6"` is created alongside the FireFastGen branch `"5"`. Both child branches `"7"` and `"8"` can safely reference the skip branch via `parent_branches: ["6"]`.

Multi-parent dedup example:

```jsonl
{"branch": "9", "component": "G1", "kind": "atomic", "output": null, "parent_branches": ["3", "7"], "step": 2, "time": "[1.994, 2.010]"}
```

**Dedup**: Branch `"9"` was reached via two distinct parent branches (`"3"` and `"7"`) that converged to the same IA-DEVS state. The simulator executed it once and recorded both contributing parents in `parent_branches`.
