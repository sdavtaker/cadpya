# Phase 3: Atomic Model Protocol + Simulator — Detailed Plan

## Goal

Extract the common pattern from Phase 2's three models into a formal `Protocol`, then build the `Simulator` engine that drives atomic models through Algorithm 1 from the paper. By the end, we can run Generator, Processor, and Counter through the Simulator with manual init + step calls.

## Branch

`phase-3-simulator` from `main`.

## Implementation Order

1. **Atomic Model Protocol** — formalize the interface all models satisfy
2. **Simulator** — Algorithm 1: init, star_function, x_function
3. **Verification tests** — run all three models through the Simulator

---

## Step 1: Atomic Model Protocol

**File**: `src/cadpya/engine/protocol.py`
**Test file**: `tests/engine/test_protocol.py`

### Design

A `Protocol` (structural subtyping) that captures the common pattern from Generator, Processor, and Counter. No base class — models are plain classes.

The Protocol uses generic type parameters for State, Time, Input, Output. Since Python Protocols with generics serve primarily as documentation and static checking (runtime `isinstance` checks don't work with generic Protocols), the Protocol's value is:

1. **Documentation**: clearly specifies what models must provide
2. **Static type checking**: mypy verifies Simulator code against the Protocol
3. **Phase 3 → Phase 5 bridge**: Coordinator will also use the Protocol

### API

```python
from typing import Protocol

from cadpya.modeling.interval import Interval


class AtomicModel[S, T, X, Y](Protocol):
    """IA-DEVS atomic model interface.

    Models are plain classes satisfying this protocol via structural
    subtyping. No inheritance required.

    Type parameters:
        S: base state type (e.g. Decimal, ProcessorState, CounterState)
        T: base time type (e.g. Decimal)
        X: base input type (e.g. Decimal, int, InputEvent)
        Y: base output type (e.g. Decimal, int)
    """

    def __init__(self, initial_state: Interval[S], initial_time: Interval[T]) -> None: ...

    def internal_transition(self) -> None: ...
    def external_transition(self, elapsed: Interval[T], x: Interval[X]) -> None: ...
    def output(self) -> Interval[Y]: ...
    def time_advance(self) -> Interval[T] | None: ...

    @property
    def state_interval(self) -> Interval[S]: ...
```

### Test cases

- **Structural conformance**: verify that Generator, Processor, and Counter satisfy the Protocol (use `typing.runtime_checkable` or mypy-only assertions)
- **Negative case**: a class missing `output()` does NOT satisfy the Protocol (mypy-only, or runtime check if `runtime_checkable`)

### Design notes

- The Protocol includes `__init__` to document the expected constructor signature. This is informational — Python Protocols don't enforce constructor signatures at runtime.
- `time_advance` returns `None` for passive (confirmed in Phase 2 — worked well, no friction).
- We do NOT include `time_interval` property in the Protocol — only the Simulator tracks `t_last`/`t_next`. Models store `_time` from init but the Simulator doesn't read it back from the model.

---

## Step 2: Simulator

**File**: `src/cadpya/engine/simulator.py`
**Test file**: `tests/engine/test_simulator.py`

### Algorithm 1 from the paper

The Simulator wraps a single atomic model and manages the simulation time bookkeeping.

#### Internal state

```python
class Simulator[S, T, X, Y]:
    __slots__ = ("_model", "_t_last", "_t_next")

    _model: AtomicModel[S, T, X, Y]
    _t_last: Interval[T]
    _t_next: Interval[T]
```

#### `init(q_state, q_time, t)`

Initialize the simulator with a total state `q = (q_state, q_time)` and current simulation time `t`.

```
model = Model(q_state, q_time)   # construct the atomic model
t_last = t - q_time              # when the last event happened
t_next = t_last + TA(state)      # when the next event is scheduled
```

If `TA(state)` returns `None` (passive), `t_next` is set to `None` (no scheduled event).

#### `star_function(t) -> Interval[Y] | None`

Process an internal event (*-function). Called when the model's scheduled event time arrives.

```
Assert t ⊆ t_next           # invariant: time must be within scheduled window
y = model.output()           # Lambda: compute output BEFORE transition
model.internal_transition()  # Delta_int: update state
t_last = t
ta = model.time_advance()
t_next = t_last + ta if ta is not None else None
return y
```

#### `x_function(x, t)`

Process an external event (x-function). Called when an input arrives from a coupled model's Z translation.

```
# Compute elapsed time since last event
if t.intersects(t_last):
    # Confluent case: event coincides with last event time
    t_local_lower = T.zero     # lower bound of elapsed = 0
    t_local_lower_closed = True
else:
    # Normal case: t_local.lower = t.lower - t_last.upper
    t_local_lower = t.lower - t_last.upper
    t_local_lower_closed = t.lower_closed and t_last.upper_closed

# Upper bound: t_local.upper = t.upper - t_last.lower
t_local_upper = t.upper - t_last.lower
t_local_upper_closed = t.upper_closed and t_last.lower_closed

t_local = Interval(t_local_lower, t_local_upper, ...)

model.external_transition(t_local, x)    # Delta_ext
t_last = t
ta = model.time_advance()
t_next = t_last + ta if ta is not None else None
```

The elapsed time computation has asymmetric bounds because `t` and `t_last` are intervals — the minimum elapsed time uses `t.lower - t_last.upper` (closest points) while the maximum uses `t.upper - t_last.lower` (farthest points). The special case when `t` intersects `t_last` clamps the lower bound to 0 (the event could be happening right at the last event time).

### Python API

```python
class Simulator[S, T, X, Y]:
    """IA-DEVS Simulator for atomic models (Algorithm 1)."""

    __slots__ = ("_model", "_t_last", "_t_next", "_model_factory", "_zero_time")

    def __init__(
        self,
        model_factory: Callable[[Interval[S], Interval[T]], AtomicModel[S, T, X, Y]],
        zero_time: T,
    ) -> None:
        """Create simulator.

        Args:
            model_factory: callable that creates the atomic model
                (typically the model class itself, e.g. Generator).
            zero_time: zero value for the time type (needed for
                elapsed time clamping in confluent case).
        """
        ...

    def init(self, q_state: Interval[S], q_time: Interval[T], t: Interval[T]) -> None:
        """Initialize simulation (Algorithm 1 init)."""
        ...

    def star_function(self, t: Interval[T]) -> Interval[Y]:
        """Process internal event (Algorithm 1 *-function)."""
        ...

    def x_function(self, x: Interval[X], t: Interval[T]) -> None:
        """Process external event (Algorithm 1 x-function)."""
        ...

    @property
    def t_last(self) -> Interval[T]:
        ...

    @property
    def t_next(self) -> Interval[T] | None:
        """None means the model is passive (no scheduled event)."""
        ...

    @property
    def model(self) -> AtomicModel[S, T, X, Y]:
        """Access the underlying model (for state inspection)."""
        ...
```

### Constructor design: `model_factory` + `zero_time`

The Simulator takes a **factory** (typically the model class itself) rather than a pre-constructed model, because `init()` needs to construct the model with `(q_state, q_time)`. This matches the paper's algorithm where the Simulator creates the model during init.

`zero_time` is needed because the elapsed time computation requires a zero value of type `T` for the confluent case (when `t` intersects `t_last`, lower elapsed = 0). Since `T` is generic, the Simulator can't construct zero on its own.

### Error handling

- `star_function` called before `init`: raise `RuntimeError`
- `x_function` called before `init`: raise `RuntimeError`
- `star_function` invariant violation (`t` not subset of `t_next`): raise `ValueError` with message referencing the formalism: `"*-function invariant violated: t=... is not a subset of t_next=..."`
- `star_function` called when passive (`t_next is None`): raise `ValueError("*-function called on passive model")`

### Handling `None` (passive) in time arithmetic

When `time_advance()` returns `None`:
- `t_next = None` (model is passive, no scheduled event)
- `star_function` cannot be called (raises error)
- `x_function` can still be called (external input wakes up a passive model)

When computing `t_next = t_last + ta`:
- If `ta is not None`: `t_next = t_last + ta` (Minkowski addition)
- If `ta is None`: `t_next = None`

### Test cases

#### With Generator

- **init from zero state**: `q_state=[0,0], q_time=[0,0], t=[0,0]` → `t_last=[0,0], t_next=[0.997,1.005]`
- **star_function at t_next**: output = `[1.997, 2.003]`, state resets to `[0,0]`, `t_next` advances
- **star_function invariant violation**: calling with `t` not subset of `t_next` raises ValueError
- **two consecutive star_function calls**: verify time progression
- **x_function between events**: elapsed computed correctly, state updated

#### With Processor

- **init passive**: empty queue → `t_next = None`
- **x_function wakes passive model**: external input enqueues job → `t_next` becomes non-None
- **star_function after input**: output = front job, state dequeues
- **star_function on passive raises**: calling star when `t_next is None` raises ValueError

#### With Counter

- **init passive**: passive(0) → `t_next = None`
- **x_function with add**: stays passive (`t_next` remains None)
- **x_function with reset**: transitions to output phase → `t_next = [0, 0]`
- **star_function immediate**: `t_next = [0, 0]`, call star at `[0, 0]` → outputs count, resets

#### Elapsed time computation

- **Normal case**: `t=[0.500, 0.600], t_last=[0.000, 0.000]` → `elapsed=[0.500, 0.600]`
- **Confluent case**: `t` intersects `t_last` → `elapsed.lower = 0, elapsed.lower_closed = True`
- **Non-trivial intervals**: `t=[0.997, 1.005], t_last=[0.500, 0.600]` → `elapsed=[0.397, 0.505]`

---

## Step 3: Verification Against Paper

Not a separate implementation step, but test cases that verify:

- Generator through Simulator matches expected time progression from the paper
- The init → star → init → star cycle produces correct `t_last`, `t_next` values
- External transitions correctly compute elapsed time and update state

These are included as part of Step 2's test cases above.

---

## File Summary

| File | Action |
|------|--------|
| `src/cadpya/engine/protocol.py` | Create |
| `src/cadpya/engine/simulator.py` | Create |
| `tests/engine/test_protocol.py` | Create |
| `tests/engine/test_simulator.py` | Create |

## Verification

After implementation:

1. `scripts/check-all.sh` passes (lint, format, mypy, pytest with 90%+ coverage)
2. All three models (Generator, Processor, Counter) can be driven through the Simulator
3. The Protocol is satisfied by all three models (verified by mypy and/or runtime checks)
4. Time bookkeeping (t_last, t_next) matches expected values from the paper's algorithm

## Design Observations to Confirm During Implementation

1. **`model_factory` vs pre-constructed model**: The plan uses a factory so `init()` can construct the model. Verify this feels ergonomic in tests. Alternative: pass a pre-constructed model and have `init()` just set time bookkeeping.

2. **`zero_time` parameter**: Needed for elapsed time clamping. Verify this isn't too awkward. Alternative: require `T` to support a `zero()` class method (but this couples the Protocol to the time type API).

3. **Generic type parameters on Simulator**: `Simulator[S, T, X, Y]` matches the Protocol. Verify mypy infers these correctly when constructing `Simulator(Generator, Decimal.zero(3))`.

4. **`t_next` as `Interval[T] | None`**: Matches `time_advance()` return type. Verify the `None` handling in star/x functions isn't too noisy.
