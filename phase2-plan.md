# Phase 2: Example Atomic Models + Supporting Types — Detailed Plan

## Goal

Build three IA-DEVS atomic models (Generator, Processor, Counter) and the supporting types they need (Decimal, Interval). By the end, we have a concrete user-facing API for atomic models — the Protocol extracted in Phase 3 will be shaped by what we discover here.

## Branch

`phase-2-atomic-models` from `main`.

## Implementation Order

Models drive the supporting types. We build in this sequence:

1. **Decimal** — needed by all models for time representation
2. **Interval** — needed by all models for uncertainty representation
3. **Generator** — simplest model, exercises scalar state + interval arithmetic
4. **Processor** — composite state (tocj + queue), exercises interval over ordered structs
5. **Counter** — discrete phase enum + count, exercises interval over non-numeric ordered types

Each step adds only the operations its model actually uses. No speculative API.

---

## Step 1: Decimal Fixed-Point Type

**File**: `src/cadpya/modeling/decimal.py`
**Test file**: `tests/modeling/test_decimal.py`

A thin wrapper around Python's `decimal.Decimal` (stdlib) that tracks a fixed number of significant decimal places (the *scale*). Every arithmetic operation quantizes its result back to the declared scale, so digits beyond the scale are never visible. No runtime dependencies — `decimal` is part of the standard library.

### API

```python
from __future__ import annotations
import decimal as _stdlib_decimal
from dataclasses import dataclass
from functools import total_ordering

@total_ordering
@dataclass(frozen=True, slots=True)
class Decimal:
    """Fixed-point decimal with tracked significant digits.

    Wraps stdlib decimal.Decimal and enforces a fixed number of
    decimal places (scale). All results are quantized to the scale
    after every operation — digits beyond it are masked.

    Decimal(3, "0.997") represents 0.997 with 3 significant decimal places.
    """
    scale: int
    _value: _stdlib_decimal.Decimal   # always quantized to `scale` places

    def __init__(self, scale: int, value: str | int | _stdlib_decimal.Decimal) -> None:
        quantizer = _stdlib_decimal.Decimal(10) ** -scale   # e.g. 0.001 for scale=3
        quantized = _stdlib_decimal.Decimal(value).quantize(quantizer)
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "_value", quantized)

    @classmethod
    def from_str(cls, scale: int, s: str) -> Decimal:
        """Create from string. Decimal.from_str(3, "0.997") == 0.997"""
        return cls(scale, s)

    @classmethod
    def from_int(cls, scale: int, whole: int) -> Decimal:
        """Create from whole units. Decimal.from_int(3, 1) == 1.000"""
        return cls(scale, whole)

    @classmethod
    def zero(cls, scale: int) -> Decimal:
        """Create zero value. Decimal.zero(3) == 0.000"""
        return cls(scale, 0)
```

### Operations needed by models

| Operation | Used by | Notes |
|-----------|---------|-------|
| `__add__` | Generator (state + elapsed), Processor (tocj + elapsed) | Same scale required; result quantized to scale |
| `__sub__` | Generator (period - state), Processor (proc_time - tocj) | Same scale required; result quantized to scale |
| `__eq__` | All models | Compares quantized `_value` fields |
| `__lt__` | All models (ordering for intervals) | Compares quantized `_value` fields |
| `__hash__` | Frozen dataclass auto-generates this; based on `(scale, _value)` |
| `__repr__` | Debugging | `Decimal(3, '0.997')` |
| `__str__` | Display | `0.997` (delegates to quantized stdlib Decimal str) |

### Scale validation

All arithmetic and comparison operators (`__add__`, `__sub__`, `__eq__`, `__lt__`) require both operands to have the **same scale**. Raise `ValueError` if scales differ — this catches bugs early and avoids implicit precision loss. The result of arithmetic is always quantized to the common scale.

### Cross-scale comparison semantics

A `Decimal(1, "1.2")` doesn't mean exactly `1.200` — it means "something in `[1.20..., 1.29...]`" because digits beyond the scale are unknown. When comparing values of different scales (e.g., `1.2` vs `1.21`), the interpretation depends on whether we're computing a lower or upper bound of an interval:

- **Lower bound context**: `1.2` → `1.200` (pad with zeros — minimum possible value)
- **Upper bound context**: `1.2` → `1.299` (pad with 9s — maximum possible value at the finer scale)

The default operators (`<`, `==`, etc.) **reject different scales** with `ValueError`. For cross-scale comparison, explicit methods are provided:

```python
def as_lower_bound(self, target_scale: int) -> Decimal:
    """Interpret this value as its minimum at a finer scale.
    Decimal(1, "1.2").as_lower_bound(3) == Decimal(3, "1.200")
    Pads with zeros.
    """
    ...

def as_upper_bound(self, target_scale: int) -> Decimal:
    """Interpret this value as its maximum at a finer scale.
    Decimal(1, "1.2").as_upper_bound(3) == Decimal(3, "1.299")
    Pads with 9s (i.e., next value at original scale minus one unit at target scale).
    Computed as: (self + 1 unit at self.scale) - (1 unit at target_scale)
    e.g., 1.2 → 1.3 - 0.001 = 1.299
    """
    ...
```

These methods require `target_scale >= self.scale` (finer or equal). Calling with a coarser target scale raises `ValueError` (lossy). The caller — typically the Interval or Simulator logic — chooses which interpretation to use based on whether it's building a lower or upper bound.

### Strict construction from strings

When constructing from a string, if there are any non-zero digits beyond the declared scale, raise `ValueError`. This catches typos early — silently truncating `Decimal(3, "0.9974")` to `0.997` would hide a bug that's hard to track down.

- `Decimal(3, "0.997")` — OK, exactly 3 decimal places
- `Decimal(3, "0.99")` — OK, fewer digits than scale (padded with zeros → `0.990`)
- `Decimal(3, "0.9970")` — OK, trailing zeros beyond scale are harmless
- `Decimal(3, "0.9974")` — **raises ValueError**: non-zero digit `4` beyond scale 3
- `Decimal(3, "1.0005")` — **raises ValueError**: non-zero digit `5` beyond scale 3

Integer inputs bypass this check (no fractional digits to validate).

### Quantization detail

After validation, the value is quantized to exactly `scale` decimal places using `ROUND_HALF_EVEN`. In practice, after the strict check above, quantization only ever pads with zeros or trims trailing zeros — it never rounds away non-zero digits. The quantizer is `10 ** -scale` (e.g., `Decimal("0.001")` for scale=3). This ensures that `str()` always shows exactly `scale` decimal places.

### Constants used by models

| Model | Constant | Decimal representation |
|-------|----------|----------------------|
| Generator | period lower = 0.997 | `Decimal(3, "0.997")` |
| Generator | period upper = 1.005 | `Decimal(3, "1.005")` |
| Generator | state upper bound = 1.005 | `Decimal(3, "1.005")` |
| Generator | output lower = 1.997 | `Decimal(3, "1.997")` |
| Generator | output upper = 2.003 | `Decimal(3, "2.003")` |
| Processor | processing time = 0.250 | `Decimal(3, "0.250")` |
| All | zero | `Decimal(3, 0)` or `Decimal.zero(3)` |

### Test cases

- Construction: from_str, from_int, zero, direct constructor with str/int
- Strict validation: `Decimal(3, "0.9974")` raises ValueError (non-zero digit beyond scale)
- Strict validation: `Decimal(3, "0.9970")` OK (trailing zero beyond scale is harmless)
- Strict validation: `Decimal(3, "0.99")` OK (fewer digits than scale, padded to `0.990`)
- Arithmetic: add, sub (same scale), result is quantized
- Arithmetic: mismatched scale raises ValueError
- Comparison: eq, lt, le, gt, ge between same-scale values
- Comparison: different scales raises ValueError
- Cross-scale lower bound: `Decimal(1, "1.2").as_lower_bound(3)` == `Decimal(3, "1.200")`
- Cross-scale upper bound: `Decimal(1, "1.2").as_upper_bound(3)` == `Decimal(3, "1.299")`
- Cross-scale upper bound edge: `Decimal(1, "1.9").as_upper_bound(3)` == `Decimal(3, "1.999")`
- Cross-scale identity: `Decimal(3, "1.200").as_lower_bound(3)` == `Decimal(3, "1.200")` (same scale is no-op)
- Cross-scale coarser target raises ValueError: `Decimal(3, "1.200").as_lower_bound(1)` raises
- Hash: equal values have equal hashes; usable as dict key / set member
- String output: `str(Decimal(3, "0.997"))` == `"0.997"`, `str(Decimal(3, 0))` == `"0.000"`
- Repr: round-trippable
- Frozen: assignment raises FrozenInstanceError

---

## Step 2: Interval Type

**File**: `src/cadpya/modeling/interval.py`
**Test file**: `tests/modeling/test_interval.py`

Generic interval over any totally-ordered type. Supports open/closed bounds and infinity.

### API

```python
@dataclass(frozen=True, slots=True)
class Interval[T]:
    lower: T
    upper: T
    lower_closed: bool
    upper_closed: bool
    lower_inf: int = 0   # -1 for -inf, 0 for finite, +1 for +inf
    upper_inf: int = 0

    # Factory methods
    @classmethod
    def closed(cls, lo: T, hi: T) -> "Interval[T]": ...
    @classmethod
    def open(cls, lo: T, hi: T) -> "Interval[T]": ...
    @classmethod
    def left_open(cls, lo: T, hi: T) -> "Interval[T]": ...
    @classmethod
    def right_open(cls, lo: T, hi: T) -> "Interval[T]": ...
    @classmethod
    def empty(cls, zero: T) -> "Interval[T]": ...

    # Infinity factories (overloads via sentinel)
    @classmethod
    def right_open_inf(cls, lo: T) -> "Interval[T]": ...   # [lo, +inf)
    @classmethod
    def open_inf(cls, lo: T) -> "Interval[T]": ...          # (lo, +inf)

    # Queries
    def is_empty(self) -> bool: ...
    def is_subset_of(self, other: "Interval[T]") -> bool: ...
    def intersects(self, other: "Interval[T]") -> bool: ...
```

### Design note on infinity factories

The Cadmia C++ implementation uses a sentinel `infinity_bound` type passed to overloaded factory methods. In Python, we can't overload by type, so we use separate named factory methods for infinity variants: `right_open_inf(lo)` for `[lo, +inf)`, `open_inf(lo)` for `(lo, +inf)`, etc. Only the variants actually used by models need to be implemented initially.

### Design note on frozen + factories

Since `Interval` is frozen, all construction goes through `@classmethod` factories. The `__init__` generated by dataclass is available but should not be called directly by user code — the factories validate invariants (lo <= hi, etc.).

### Operations needed by models

| Operation | Used by | Notes |
|-----------|---------|-------|
| `Interval.closed(lo, hi)` | All models | Most common factory |
| `Interval.empty(zero)` | Processor (passive), Counter (passive) | Represents ta = empty set |
| `Interval.right_open_inf(lo)` | Counter (mixed phase ta), Processor (mixed queue ta) | `[lo, +inf)` |
| `__add__` (Minkowski) | Generator (state + elapsed, t_last + ta), Simulator will use this | `[a,b] + [c,d] = [a+c, b+d]` |
| `__sub__` (interval) | Generator (period - state), Simulator (t - t_last) | `[a,b] - [c,d] = [a-d, b-c]` |
| `is_empty()` | All models, Simulator | Check for passive state |
| `is_subset_of()` | Simulator (*-function invariant check) | `t ⊆ t_next` |
| `intersects()` | Coordinator (imminent detection) | `t_next ∩ t ≠ ∅` |
| `__eq__` | Tests, state comparison | Value equality |
| `__repr__` | Debugging | `Interval.closed(Decimal(3, 997), Decimal(3, 1005))` |
| `__str__` | Display | `[0.997, 1.005]` |

### Minkowski addition rules

```
[a, b] + [c, d] = [a+c, b+d]
closed + closed = closed
closed + open = open (on the open side)
any + empty = empty
infinity + finite = infinity (same sign)
```

Closure: `result_lower_closed = a.lower_closed and b.lower_closed` (both must be closed for result to be closed). Same for upper.

### Interval subtraction rules

```
[a, b] - [c, d] = [a-d, b-c]   (note: subtract upper from lower and vice versa)
closed - closed = closed
any - empty = empty
```

Closure: `result_lower_closed = a.lower_closed and b.upper_closed`. Upper: `a.upper_closed and b.lower_closed`.

### Overflow to infinity

When T is `Decimal` (backed by Python int), overflow is not a concern since Python ints are arbitrary precision. We do NOT need overflow policies for the Python implementation. This is a simplification over Cadmia's C++ version.

### Test cases

- Factory methods: closed, open, left_open, right_open, empty, right_open_inf
- Validation: hi < lo raises ValueError
- is_empty: empty interval returns True, non-empty returns False
- Minkowski addition: closed+closed, closed+open, with infinity, with empty
- Interval subtraction: closed-closed, with infinity, with empty
- is_subset_of: proper subset, equal, not subset, empty subset of anything
- intersects: overlapping, non-overlapping, touching open endpoints, empty
- String representations: `[0.997, 1.005]`, `(0, 0)` (empty), `[0.000, +inf)`
- Frozen: assignment raises

---

## Step 3: Generator Model

**File**: `src/cadpya/basic_models/generator.py`
**Test file**: `tests/basic_models/test_generator.py`

The simplest IA-DEVS model. Scalar state, periodic output with uncertainty.

### From the paper (Generator_IA)

- **State**: accumulated time since last output, in `[0, 1.005]`
- **Period**: `[0.997, 1.005]` (uncertainty in tick frequency)
- **Output**: `[1.997, 2.003]` (uncertainty in output value)
- **delta_int**: reset state to `[0, 0]`
- **delta_ext**: state = state + elapsed (track time, ignore input)
- **lambda**: always `[1.997, 2.003]`
- **ta**: period - state, clamped to `[0, +inf)`

### Python API

```python
class Generator:
    # Type aliases — used in method signatures for clarity
    type State = Decimal
    type Time = Decimal
    type Input = Decimal       # unused but defined for protocol conformance
    type Output = Decimal

    def __init__(self, initial_state: Interval[State], initial_time: Interval[Time]) -> None:
        """Set initial state and simulation time (called by simulator init())."""
        ...

    def internal_transition(self) -> None: ...
    def external_transition(self, elapsed: Interval[Time], x: Interval[Input]) -> None: ...
    def output(self) -> Interval[Output]: ...
    def time_advance(self) -> Interval[Time] | None: ...

    @property
    def state_interval(self) -> Interval[State]: ...
```

`time_advance` returns `None` for passive (empty set in formalism). The Generator never becomes passive on its own, so it always returns an interval.

### Constants (class-level)

```python
SCALE = 3
PERIOD = Interval.closed(Decimal(3, "0.997"), Decimal(3, "1.005"))
OUTPUT = Interval.closed(Decimal(3, "1.997"), Decimal(3, "2.003"))
ZERO_STATE = Interval.closed(Decimal.zero(3), Decimal.zero(3))
```

### Test cases

- **Construction**: initial state `[0, 0]`, verify state_interval
- **time_advance**: from `[0, 0]` → `[0.997, 1.005]` (period - 0)
- **time_advance**: from `[0.100, 0.200]` → `[0.797, 0.905]`
- **output**: always returns `[1.997, 2.003]`
- **internal_transition**: resets state to `[0, 0]`
- **external_transition**: state = state + elapsed (e.g., `[0, 0]` + `[0.5, 0.5]` → `[0.5, 0.5]`)
- **external_transition**: ignores input x
- **Validation**: state outside `[0, 1.005]` raises error

---

## Step 4: Processor Model

**File**: `src/cadpya/basic_models/processor.py`
**Test file**: `tests/basic_models/test_processor.py`

Composite state: time-on-current-job (tocj) + job queue. Exercises intervals over user-defined ordered structs.

### From the paper (Processor_IA)

- **State**: `(tocj: Decimal, qj: deque[int])` — tocj in `[0, 0.250]`, qj is FIFO of job IDs
- **Processing time**: fixed `Decimal(3, "0.250")` (no uncertainty in processor itself)
- **delta_int**: dequeue front job, reset tocj to 0. If queue becomes empty → passive.
- **delta_ext**: enqueue new job, update tocj += elapsed
- **lambda**: output = front of queue (interval from lower.qj.front to upper.qj.front)
- **ta**: `[proc_time - tocj_upper, proc_time - tocj_lower]` when queue non-empty, `None` when empty

### State type with ordering

```python
@total_ordering
@dataclass(frozen=True, slots=True)
class ProcessorState:
    tocj: Decimal
    qj: tuple[int, ...]   # frozen tuple for hashability

    def __lt__(self, other: "ProcessorState") -> bool:
        # Order by tocj first, then queue size, then elements
        if self.tocj != other.tocj:
            return self.tocj < other.tocj
        if len(self.qj) != len(other.qj):
            return len(self.qj) < len(other.qj)
        return self.qj < other.qj

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProcessorState):
            return NotImplemented
        return self.tocj == other.tocj and self.qj == other.qj
```

**Note**: We use `tuple[int, ...]` instead of `deque` for the queue because `ProcessorState` must be frozen/hashable to work inside frozen `Interval`. The model methods create new tuples when enqueuing/dequeuing.

### Interval over ProcessorState

`Interval[ProcessorState]` works because ProcessorState is totally ordered. The lower/upper bounds are complete ProcessorState values. Transition functions manipulate `.lower` and `.upper` independently.

### Key behavior patterns

**internal_transition**:
- Lower state: tocj=0, qj = lower.qj[1:] (pop front)
- Upper state: tocj=0, qj = upper.qj[1:]
- If either queue becomes empty after pop → becomes passive (return empty interval or handle mixed case)

**external_transition(elapsed, x)**:
- Lower state: tocj = lower.tocj + elapsed.lower, qj = lower.qj + (x.lower,)
- Upper state: tocj = upper.tocj + elapsed.upper, qj = upper.qj + (x.upper,)

**output**:
- `Interval.closed(lower.qj[0], upper.qj[0])`

**time_advance**:
- Both queues non-empty: `Interval.closed(proc_time - upper.tocj, proc_time - lower.tocj)`
- Both queues empty: `None` (passive)
- Mixed (lower empty, upper non-empty): `Interval.right_open_inf(proc_time - upper.tocj)` — `[val, +inf)`

### Python API

```python
class Processor:
    # Type aliases
    type State = ProcessorState
    type Time = Decimal
    type Input = int
    type Output = int

    def __init__(self, initial_state: Interval[State], initial_time: Interval[Time]) -> None:
        """Set initial state and simulation time (called by simulator init())."""
        ...

    def internal_transition(self) -> None: ...
    def external_transition(self, elapsed: Interval[Time], x: Interval[Input]) -> None: ...
    def output(self) -> Interval[Output]: ...
    def time_advance(self) -> Interval[Time] | None: ...

    @property
    def state_interval(self) -> Interval[State]: ...
```

### Test cases

- **Construction**: empty queue state + initial time, verify passive (time_advance returns None)
- **external_transition**: enqueue job 1, verify state has job in queue, time_advance returns `[0.250, 0.250]`
- **external_transition**: enqueue multiple jobs, verify queue order
- **output**: returns front job ID as interval
- **internal_transition**: dequeues front job, resets tocj
- **internal_transition**: last job dequeued → becomes passive
- **time_advance**: with elapsed time accumulated in tocj
- **Mixed queue case**: lower empty, upper non-empty → `[val, +inf)`

---

## Step 5: Counter Model

**File**: `src/cadpya/basic_models/counter.py`
**Test file**: `tests/basic_models/test_counter.py`

Discrete phase + count. Exercises intervals over enum-ordered states.

### Behavior

- **Phase**: `passive` or `output` (passive < output in ordering)
- **Input events**: `add` or `reset` (add < reset in ordering)
- **Add event**: increment count, stay passive
- **Reset event**: transition to output phase (ta = 0, immediate output)
- **Internal transition**: output count, reset to (passive, 0)
- **Uncertain input `[add, reset]`**: spans both behaviors — lower stays passive, upper becomes output

### State type

```python
class Phase(enum.IntEnum):
    PASSIVE = 0
    OUTPUT = 1

class InputEvent(enum.IntEnum):
    ADD = 0
    RESET = 1

@total_ordering
@dataclass(frozen=True, slots=True)
class CounterState:
    phase: Phase
    count: int

    def __lt__(self, other: "CounterState") -> bool:
        if self.phase != other.phase:
            return self.phase < other.phase
        return self.count < other.count

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CounterState):
            return NotImplemented
        return self.phase == other.phase and self.count == other.count
```

### time_advance patterns

| Lower phase | Upper phase | Result |
|-------------|-------------|--------|
| passive | passive | `None` (passive) |
| output | output | `[0, 0]` (immediate) |
| passive | output | `[0, +inf)` (uncertain) |
| output | passive | Invalid (error) |

### Python API

```python
class Counter:
    # Type aliases
    type State = CounterState
    type Time = Decimal
    type Input = InputEvent
    type Output = int

    def __init__(self, initial_state: Interval[State], initial_time: Interval[Time]) -> None:
        """Set initial state and simulation time (called by simulator init())."""
        ...

    def internal_transition(self) -> None: ...
    def external_transition(self, elapsed: Interval[Time], x: Interval[Input]) -> None: ...
    def output(self) -> Interval[Output]: ...
    def time_advance(self) -> Interval[Time] | None: ...

    @property
    def state_interval(self) -> Interval[State]: ...
```

### Test cases

- **Construction**: passive state with count=0 + initial time
- **external_transition with add**: count increments, stays passive
- **external_transition with reset**: transitions to output phase
- **external_transition with [add, reset]**: lower passive, upper output
- **internal_transition from output**: resets to (passive, 0)
- **internal_transition from mixed [passive, output]**: lower resets to (passive, 0), upper keeps count
- **output**: returns count interval
- **time_advance**: all four phase combinations from table above

---

## File Summary

| File | Action |
|------|--------|
| `src/cadpya/modeling/decimal.py` | Create |
| `src/cadpya/modeling/interval.py` | Create |
| `src/cadpya/basic_models/generator.py` | Create |
| `src/cadpya/basic_models/processor.py` | Create |
| `src/cadpya/basic_models/counter.py` | Create |
| `tests/modeling/test_decimal.py` | Create |
| `tests/modeling/test_interval.py` | Create |
| `tests/basic_models/test_generator.py` | Create |
| `tests/basic_models/test_processor.py` | Create |
| `tests/basic_models/test_counter.py` | Create |

## Verification

After implementation:

1. `scripts/check-all.sh` passes (lint, format, mypy, pytest with 90%+ coverage)
2. All three models can be constructed, have transitions called, and produce expected interval results
3. The common pattern across all three models is clear enough to extract a Protocol in Phase 3

## Design Observations to Confirm During Implementation

These are things we'll discover as we code. Document findings for Phase 3:

1. **Should `time_advance` return `None` or `Interval.empty()`?** The plan says `None` for ergonomics, but we may find `Interval.empty()` composes better with interval arithmetic in the Simulator. Try `None` first and see.

2. **State mutation pattern**: Models own `_state: Interval[S]` and mutate it in transition functions. This matches Cadmia. Verify this feels natural in Python.

3. **Type aliases (resolved)**: Models use Python 3.12+ `type` statement aliases (`type State = Decimal`, etc.) and reference them in method signatures. Verify mypy handles these correctly and that the Phase 3 Protocol can reference them.

4. **String representations**: Each model needs `__str__` or similar for logging. Decide if this belongs on the model or is handled externally.
