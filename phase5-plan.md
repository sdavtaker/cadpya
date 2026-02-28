# Phase 5: Coordinator + Root Coordinator + Branching — Detailed Plan

## Goal

Implement the Coordinator (Algorithms 2-3), Root Coordinator (Algorithm 4), and BFS branching mechanism. By the end, we can run the 4GP case study end-to-end and verify results against the paper's Tables 1-5.

## Branch

`phase-5-coordinator` from `main`.

## Implementation Order

1. **EIC coupled model example** — new test exercising External Input Coupling
2. **Engine Protocol** — common interface for Simulator and Coordinator
3. **Coordinator** — init, BoundTs, star_function, x_function, route
4. **Root Coordinator** — main simulation loop with BFS queue
5. **Tests with GP** — simple coupled model (no branching)
6. **Tests with 4GP** — paper case study (branching, verification against tables)
7. **Tests with hierarchical model** — nested Coordinators
8. **Tests with EIC model** — EIC routing through sub-Coordinator

---

## Step 0: EIC Coupled Model Example

**File**: `tests/coupled_models/test_eic.py`

### Description

A fourth coupled model example that exercises External Input Coupling (EIC). None of the existing examples (GP, 4GP, hierarchical) route external input into a sub-coupled model.

The topology: two coupled models connected at the top level.

```
Top-level:
  Generators = CoupledModel(G1, G2) --[Z_{Generators,GPP}]--> GPP
  GPP = CoupledModel(G3, G4, P)     --[Z_{GPP,self}]--------> (output)

Generators (sub-coupled, EOC only):
  G1 --[Z_{G1,self}]--> (output)    [job 1]
  G2 --[Z_{G2,self}]--> (output)    [job 2]

GPP (sub-coupled, has EIC + IC + EOC):
  (input) --[Z_{self,P}]--> P       [EIC: external input routed to P]
  G3 --[Z_{G3,P}]---------> P       [IC: job 3]
  G4 --[Z_{G4,P}]---------> P       [IC: job 4]
  P  --[Z_{P,self}]-------> (output) [EOC]
```

This is semantically equivalent to the flat 4GP model: 4 generators all feed 1 processor, producing the same set of reachable trajectories. But the routing path for G1/G2's output goes: G1 fires → Generators EOC → top-level Z → GPP EIC → GPP's internal Z_{self,P} → P's x_function.

### Key: EIC in the GPP sub-model

The GPP sub-coupled model has `"self"` as an influencer of `"P"`:
- `influencers["P"] = frozenset({"G3", "G4", "self"})` — G3, G4, and external input all influence P
- `translations[("self", "P")]` = identity (pass through the job ID interval)

This exercises the `x_function` path in the Coordinator: when the GPP Coordinator receives an external event, it routes it to P via `Z_{self,P}`.

### Components

**Generators sub-model:**
- `"G1"`, `"G2"`: Generator instances
- `I["G1"] = I["G2"] = frozenset()`
- `I["self"] = frozenset({"G1", "G2"})` — both produce external output
- `Z_{G1,self}`: → job 1, `Z_{G2,self}`: → job 2

**GPP sub-model:**
- `"G3"`, `"G4"`: Generator instances
- `"P"`: Processor instance
- `I["G3"] = I["G4"] = frozenset()`
- `I["P"] = frozenset({"G3", "G4", "self"})` — **"self" here is the EIC**
- `I["self"] = frozenset({"P"})` — EOC
- `Z_{self,P}`: identity (EIC), `Z_{G3,P}`: → job 3, `Z_{G4,P}`: → job 4, `Z_{P,self}`: identity

**Top-level:**
- `"Generators"`: coupled spec (Generators sub-model)
- `"GPP"`: coupled spec (GPP sub-model)
- `I["Generators"] = frozenset()`
- `I["GPP"] = frozenset({"Generators"})` — Generators output feeds GPP
- `I["self"] = frozenset({"GPP"})` — GPP output is external
- `Z_{Generators,GPP}`: identity, `Z_{GPP,self}`: identity

### Test cases (data structure only — simulation in Step 8)

- Construct Generators sub-model — validation passes
- Construct GPP sub-model — validation passes, `"self"` in `I["P"]`
- Construct top-level — validation passes
- Verify GPP has EIC: `"self"` in `influencers["P"]`
- Verify `("self", "P")` in GPP translations
- Call `Z_{self,P}` with job ID interval → identity pass-through

---

## Step 1: Engine Protocol

**File**: `src/cadpya/engine/protocol.py` (extend existing file)

### Design

Both Simulator and Coordinator implement the same interface so the Coordinator can treat child engines uniformly. We add an `Engine` Protocol alongside the existing `AtomicModel` Protocol.

```python
@runtime_checkable
class Engine[T, Y](Protocol):
    """Common interface for Simulator and Coordinator.

    The Coordinator treats child engines uniformly through this interface.
    """

    def init(self, q: Any, q_time: Interval[T], t: Interval[T]) -> None: ...
    def star_function(self, t: Interval[T]) -> Interval[Y] | None: ...
    def x_function(self, x: Interval[Any], t: Interval[T]) -> None: ...

    @property
    def t_last(self) -> Interval[T]: ...

    @property
    def t_next(self) -> Interval[T] | None: ...
```

### Simulator conformance

The existing `Simulator` already has `star_function`, `x_function`, `t_last`, `t_next`. Its `init(q_state, q_time, t)` signature matches. Its `star_function` returns `Interval[Y]` (never None for atomic models), which satisfies `Interval[Y] | None`.

### Coordinator conformance

The Coordinator will return `Interval[Y] | None` from `star_function` — `None` when the output is consumed internally (no EOC).

### Test cases

- Simulator satisfies Engine Protocol
- Coordinator satisfies Engine Protocol (after Step 2)

---

## Step 2: Coordinator

**File**: `src/cadpya/engine/coordinator.py`
**Test file**: `tests/engine/test_coordinator.py`

### Internal state

```python
class Coordinator[T, Y]:
    _coupled_model: CoupledModel[T]
    _zero_time: T
    _engines: dict[str, Engine]  # child engines (Simulators or sub-Coordinators)
    _t_last: Interval[T] | None
    _t_next: Interval[T] | None
```

### init(q, t)

From Algorithm 2 (paper lines 808-818):

```python
def init(self, q: dict[str, Any], q_time: dict[str, Interval[T]], t: Interval[T]) -> None:
    for name, spec in self._coupled_model.components.items():
        if spec.is_atomic:
            engine = Simulator(spec.model_factory, self._zero_time)
            engine.init(spec.initial_state, spec.initial_elapsed, t)
        else:
            engine = Coordinator(spec.coupled_model, self._zero_time)
            engine.init(...)  # recursive
        self._engines[name] = engine
    self._bound_ts()
```

**Design decision — init parameters**: The paper's init receives `q` (a tuple of init values indexed by model ID) and `t`. Since our `ComponentSpec` already contains `initial_state` and `initial_elapsed`, the Coordinator can read them directly from the coupled model definition. The `init` method only needs `t` (the simulation start time).

Simplified signature:

```python
def init(self, t: Interval[T]) -> None:
```

This is cleaner than forcing users to construct a parallel dict of init values. The ComponentSpec already bundles everything.

### BoundTs()

From Algorithm 2 (paper lines 827-836):

```python
def _bound_ts(self) -> None:
    active = [(name, eng) for name, eng in self._engines.items()
              if eng.t_next is not None]

    if not active:
        self._t_next = None  # all passive
        # t_last from all engines
        ...
        return

    # t_last: max of all children's t_last endpoints
    t_last_lower = max(eng.t_last.lower for eng in self._engines.values())
    t_last_upper = max(eng.t_last.upper for eng in self._engines.values())
    t_last_lower_closed = ...  # closed if exists i that includes it AND no j that excludes it
    t_last_upper_closed = ...  # closed if any child includes that endpoint

    # t_next: min of active children's t_next endpoints
    t_next_lower = min(eng.t_next.lower for _, eng in active)
    t_next_upper = min(eng.t_next.upper for _, eng in active)
    t_next_lower_closed = ...  # same closedness logic
    t_next_upper_closed = ...
```

**Closedness logic from the paper** (line 831):

For `t_last.lower_closed`:
- Closed if there exists engine `i` where `E[i].t_last.lower == t_last.lower` AND `E[i].t_last.lower_closed` is True
- AND there does NOT exist engine `j` where `E[j].t_last.lower == t_last.lower` AND `E[j].t_last.lower_closed` is False

Translation: closed if at least one child includes the endpoint, and no child at that same value excludes it. If there's a conflict (one includes, another excludes at same value), the result is open.

For `t_last.upper_closed`: closed if any child includes that endpoint value (simpler — paper line 830: `∃i : t_last.upperend ∈ E[i].t_last`).

For `t_next`: same logic as `t_last` but using `min` instead of `max`.

### star_function(t)

From Algorithm 3 (paper lines 844-882). This is the most complex algorithm.

```python
def star_function(self, t: Interval[T]) -> Interval[Y] | None:
    # 1. Find imminent engines
    imminents = [name for name, eng in self._engines.items()
                 if eng.t_next is not None and eng.t_next.intersects(t)]

    # 2. Sort by << ordering on t_next
    imminents.sort(key=lambda name: (self._engines[name].t_next.lower,
                                      self._engines[name].t_next.upper))

    # 3. Compute limit
    first_eng = self._engines[imminents[0]]
    limit = first_eng.t_next.intersection(t)

    # Restrict upper bound if later imminents exist
    for name in imminents:
        eng = self._engines[name]
        if has_values_after(eng.t_next, first_eng.t_next):
            limit = restrict_upper(limit, eng.t_next.lower, eng.t_next.lower_closed)
            break

    # 4. Check if punctual
    if limit.is_punctual():
        # SELECT
        candidates = frozenset(
            name for name in imminents
            if self._engines[name].t_next.intersects(limit)
        )
        chosen = self._coupled_model.select(candidates)

        # FORK if limit strictly inside chosen's t_next
        if limit != self._engines[chosen].t_next:
            yield Fork(
                action=lambda: subtract_and_recurse(chosen, limit, t)
            )

        # Main branch: route chosen engine
        y = self._route(chosen, limit)
        self._bound_ts()
        return y

    else:
        # Non-punctual: FORK for each imminent
        relevant = [name for name in imminents
                    if self._engines[name].t_next.intersects(limit)]
        for name in relevant:
            yield Fork(
                action=lambda: route_and_bound(name, limit)
            )

        # After all branches: subtract limit or EXIT
        if all(not (eng.t_next - limit).is_empty()
               for name in imminents
               for eng in [self._engines[name]]):
            for name in imminents:
                self._engines[name].t_next -= limit
        else:
            return None  # EXIT — simulation terminates
```

**FORK mechanism**: The star_function cannot literally yield forks (that would require generators and change the API). Instead, it returns a `StepResult` that encodes what happened:

```python
@dataclass
class StepResult[T, Y]:
    output: Interval[Y] | None  # output for this branch (None = internal)
    forks: list[ForkSpec]       # branches to create (each is a state snapshot)
```

But this couples the Coordinator to the branching mechanism. Cleaner approach: **the Root Coordinator drives the branching**, not the Coordinator itself.

### Alternative: Coordinator reports forks, Root Coordinator executes them

The Coordinator's `star_function` returns the list of possible actions (which engine to advance, with what limit) and the Root Coordinator:
1. Clones state for each fork
2. Executes each fork on its clone
3. Enqueues all results

This separates concerns: the Coordinator computes what branches exist, the Root Coordinator manages the BFS queue and cloning.

**Revised star_function return type**:

```python
@dataclass(frozen=True, slots=True)
class BranchAction:
    """One possible action in the current step."""
    engine_name: str
    limit: Interval[T]

@dataclass(frozen=True, slots=True)
class StepResult[T, Y]:
    """Result of a Coordinator star_function call."""
    branches: list[BranchAction]     # possible branches
    subtract_limit: Interval[T] | None  # if set, subtract from imminents after branching
```

But this changes the Engine interface (Simulator returns output, Coordinator returns StepResult). We need uniformity.

**Final design: Coordinator executes one branch, Root Coordinator handles cloning**

The Root Coordinator:
1. Asks the Coordinator "what are the possible branches?" via `compute_branches(t)`
2. For each branch, clones the state
3. Calls `execute_branch(branch)` on each clone

```python
class Coordinator[T, Y]:
    def compute_branches(self, t: Interval[T]) -> list[BranchAction]:
        """Compute possible branches without executing any."""
        ...

    def execute_branch(self, action: BranchAction) -> Interval[Y] | None:
        """Execute one branch: route the chosen engine, update BoundTs."""
        y = self._route(action.engine_name, action.limit)
        self._bound_ts()
        return y

    def subtract_limit(self, limit: Interval[T], imminents: list[str]) -> None:
        """Subtract limit from imminent engines' t_next (after all branches forked)."""
        ...
```

This keeps the Coordinator focused on the algorithm and lets the Root Coordinator handle the BFS queue. The Engine Protocol's `star_function` is only used by the Simulator; the Coordinator exposes a richer API that the Root Coordinator calls directly.

### route(engine_name, t)

From Algorithm 3 (paper lines 884-890):

```python
def _route(self, engine_name: str, t: Interval[T]) -> Interval[Y] | None:
    eng = self._engines[engine_name]
    y = eng.star_function(t)

    # Route output to influenced engines
    for dest in self._coupled_model.influencers.get(engine_name, frozenset()):
        if dest == "self":
            continue  # EOC handled below
        z = self._coupled_model.translations[(engine_name, dest)]
        x_translated = z(y)
        self._engines[dest].x_function(x_translated, t)

    # Check for EOC (output to parent)
    if "self" in self._coupled_model.influencers and \
       engine_name in self._coupled_model.influencers["self"]:
        z_eoc = self._coupled_model.translations[(engine_name, "self")]
        return z_eoc(y)

    return None
```

### x_function(x, t)

From Algorithm 2 (paper lines 820-825):

```python
def x_function(self, x: Interval[Any], t: Interval[T]) -> None:
    # Route external input to influenced sub-models
    if "self" in self._coupled_model.influencers:
        for dest in self._coupled_model.influencers.get("self", frozenset()):
            # Wait, influencers["self"] contains sources of EOC, not EIC targets
            ...
```

**Clarification on influencer semantics for EIC**:

In the current CoupledModel design, `influencers[dest]` lists the sources that influence `dest`. For EIC:
- `influencers["P"] = {"self"}` would mean "self (external input) influences P"
- Translation: `("self", "P")` in translations

The x_function iterates over components influenced by "self":

```python
def x_function(self, x: Interval[Any], t: Interval[T]) -> None:
    for dest, sources in self._coupled_model.influencers.items():
        if "self" in sources and dest != "self":
            z = self._coupled_model.translations[("self", dest)]
            x_translated = z(x)
            self._engines[dest].x_function(x_translated, t)
    self._bound_ts()
```

**Note**: The current examples (GP, 4GP) don't use EIC (no external input to the top model). EIC will be needed for hierarchical models where a parent sends input to a sub-Coordinator.

### Interval operations needed

The Coordinator needs two new operations on Interval:

1. **`intersection(other)`**: Compute `self ∩ other`. Needed for limit computation.
2. **`is_punctual()`**: True if `lower == upper` and both closed. Needed for branch decision.

These should be added to `Interval[T]` in `src/cadpya/modeling/interval.py`.

### Test cases (with GP model — no branching)

- **init**: Coordinator creates Simulator for G and P, BoundTs computes correct t_last/t_next
- **compute_branches at t_next**: single imminent (G), limit = G's t_next, no branching
- **execute_branch**: G fires, output routed to P via Z, P receives x_function
- **After first step**: G's state reset, P has job 1 queued, t_next updated
- **Second step**: P fires (only imminent), outputs job 1, queue empty → passive

---

## Step 3: Root Coordinator

**File**: `src/cadpya/engine/root_coordinator.py`
**Test file**: `tests/engine/test_root_coordinator.py`

### Design

The Root Coordinator manages the BFS simulation queue. Each queue entry is a complete simulation state (a Coordinator with all its children). Branching clones the state.

```python
@dataclass
class SimulationBranch[T]:
    """One branch of the simulation tree."""
    branch_id: str
    coordinator: Coordinator[T, Any]
    parent_branch_id: str | None
    step: int

class RootCoordinator[T]:
    def simulate(
        self,
        coupled_model: CoupledModel[T],
        t: Interval[T],
        max_steps: int | None = None,
        max_branches: int | None = None,
    ) -> list[LogEntry]:
        """Run BFS simulation, returning structured log."""
        ...
```

### BFS Main Loop (Algorithm 4 + branching)

```python
def simulate(self, coupled_model, t, max_steps=None, max_branches=None):
    # Create initial branch
    coord = Coordinator(coupled_model, coupled_model.zero_time)
    coord.init(t)
    queue = deque([SimulationBranch("0", coord, None, 0)])
    log = []

    while queue:
        branch = queue.popleft()
        if branch.coordinator.t_next is None:
            continue  # passive — discard, no future events possible

        t_current = branch.coordinator.t_next

        # Compute possible branches
        actions = branch.coordinator.compute_branches(t_current)

        if len(actions) == 1:
            # No branching — execute in place
            output = branch.coordinator.execute_branch(actions[0])
            log_step(log, branch, actions[0], output)
            branch.step += 1
            # Only re-enqueue if still active (not passive)
            if branch.coordinator.t_next is not None:
                queue.append(branch)
            # else: passive — discard safely
        else:
            # Branching — clone state for each branch
            for i, action in enumerate(actions):
                clone = deep_clone(branch.coordinator)
                output = clone.execute_branch(action)
                new_branch = SimulationBranch(
                    f"{branch.branch_id}.{i}",
                    clone,
                    branch.branch_id,
                    branch.step + 1,
                )
                log_step(log, new_branch, action, output)
                # Only enqueue branches that are still active
                if clone.t_next is not None:
                    queue.append(new_branch)
                # else: passive — discard safely, no more events

    return log
```

### State cloning

Deep copy of the entire Coordinator tree using `copy.deepcopy()`. The CoupledModel definition is immutable (frozen dataclass) and can be shared — only the engine state needs cloning.

For efficiency, Simulator and Coordinator should implement `__deepcopy__` to skip cloning the immutable CoupledModel reference:

```python
def __deepcopy__(self, memo):
    cls = type(self)
    result = cls.__new__(cls)
    memo[id(self)] = result
    # Share coupled_model (immutable), deep copy everything else
    result._coupled_model = self._coupled_model  # shared reference
    result._zero_time = self._zero_time           # immutable
    result._engines = copy.deepcopy(self._engines, memo)
    result._t_last = copy.deepcopy(self._t_last, memo)
    result._t_next = copy.deepcopy(self._t_next, memo)
    return result
```

### Structured log output

Each step produces a log entry (JSON-serializable dict):

```python
@dataclass(frozen=True, slots=True)
class LogEntry:
    step: int
    branch: str
    parent_branch: str | None
    time: str           # str repr of Interval
    component: str
    operation: str      # "init" | "internal" | "external" | "output" | "fork"
    state: str | None
    output: str | None
    input: str | None
    t_next: str | None
```

### Passive branch pruning

Branches that reach passivity (`t_next is None`) are terminal — no future events are possible. These branches are safely discarded from the BFS queue instead of being re-enqueued. This is a natural pruning mechanism that bounds the queue growth: any branch where all engines have fired their last event and no more transitions are scheduled is simply dropped.

### Safety limits

The BFS queue can grow exponentially. Safety parameters (in addition to passive pruning):
- `max_steps`: total steps across all branches (default: 10000)
- `max_branches`: maximum number of active branches (default: 1000)

When exceeded, raise `SimulationLimitError`.

### Test cases

- **GP simulation**: init → G fires → P receives → P fires → passive. No branching. Verify outputs.
- **4GP first wave**: 4 branches created (one per generator). Verify 4 branches after first step.
- **4GP full first wave**: 24 branches after all 4 generators fire. Verify processor states.
- **Verify against Table 1**: initialization values match paper.
- **Verify against Table 2**: first step (G1 branch) state matches paper.
- **Verify against Table 3**: after 4 steps (G1-G2-G3-G4 branch) matches paper.
- **max_steps limit**: simulation stops when limit reached.

---

## Step 4: New Interval Operations

**File**: `src/cadpya/modeling/interval.py` (extend)
**Test file**: `tests/modeling/test_interval.py` (extend)

### `intersection(other) -> Interval[T]`

Compute the intersection of two intervals:

```python
def intersection(self, other: Interval[T]) -> Interval[T]:
    if self.is_empty() or other.is_empty():
        return self.empty(self.lower)  # empty
    if not self.intersects(other):
        return self.empty(self.lower)  # empty

    # Lower bound: max of the two lowers
    # Upper bound: min of the two uppers
    # Closedness: intersection of closedness at each bound
    ...
```

### `is_punctual() -> bool`

True if the interval contains exactly one value:

```python
def is_punctual(self) -> bool:
    return (not self.is_empty()
            and self.lower == self.upper
            and self.lower_closed and self.upper_closed
            and self.lower_inf == 0 and self.upper_inf == 0)
```

### Test cases

- intersection of overlapping closed intervals
- intersection of non-overlapping intervals → empty
- intersection with empty → empty
- intersection where one contains the other
- intersection at single point (touching closed endpoints)
- is_punctual for `[1, 1]` → True
- is_punctual for `[1, 2]` → False
- is_punctual for `(1, 1)` → False (empty)
- is_punctual for empty → False

---

## File Summary

| File | Action |
|------|--------|
| `src/cadpya/modeling/interval.py` | Extend with `intersection`, `is_punctual` |
| `src/cadpya/engine/protocol.py` | Add `Engine` Protocol |
| `src/cadpya/engine/coordinator.py` | Create |
| `src/cadpya/engine/root_coordinator.py` | Create |
| `tests/modeling/test_interval.py` | Extend |
| `tests/engine/test_coordinator.py` | Create |
| `tests/engine/test_root_coordinator.py` | Create |
| `CLAUDE.md` | Update with Coordinator/RootCoordinator notes |

## Verification

After implementation:

1. `scripts/check-all.sh` passes
2. GP model runs end-to-end through Root Coordinator without branching
3. 4GP model produces correct branches (4 after first step, 24 after first wave)
4. Initialization values match paper Table 1
5. First step values (G1 branch) match paper Table 2
6. Four-step values (G1-G2-G3-G4 branch) match paper Table 3
7. Hierarchical model produces equivalent behavior to flat 4GP
8. Safety limits prevent runaway simulation

## Design Questions to Resolve During Implementation

1. **Coordinator init signature**: The plan simplifies init to `init(t)` since ComponentSpec has the initial state. Verify this works for nested Coordinators too.

2. **`compute_branches` + `execute_branch` split**: This separates branch computation from execution. Verify the Coordinator can cleanly separate these without executing side effects in compute_branches.

3. **Interval subtraction for limit**: The paper uses `E.t_next = E.t_next - limit` after branching. Our current Interval subtraction produces a single interval (lower bound of result). For non-punctual limit subtraction from a wider interval, this should work naturally. For punctual subtraction from a wider interval (e.g., `[0.997, 1.005] - [1.0, 1.0]`), the result should be the upper portion `(1.0, 1.005]`. Verify our subtraction handles this.

4. **Deep copy performance**: For the 4GP case study, 24 branches means 24 deep copies. Verify this is fast enough. Optimization (shared immutable state) can be deferred.

5. **Route function and influencer iteration**: The route function iterates over influencers of the engine that just fired. Verify the influencer dict lookup is correct — `influencers` maps `dest → {sources}`, so to find "who does engine X influence", we need to scan all dests.
