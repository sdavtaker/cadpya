# Phase 4: Coupled Model Data Structure + Examples — Detailed Plan

## Goal

Define the coupled model data structure and build three example coupled models of increasing complexity, before formalizing the Coordinator engine in Phase 5. By the end, we have a validated `CoupledModel` data structure and three fully specified coupled model instances (with component specs, influencers, translation functions, and SELECT), ready for the Coordinator to consume.

## Branch

`phase-4-coupled` from `main`.

## Implementation Order

1. **Component specification** — how to describe a sub-model and its initial state
2. **Coupled model data structure** — the `C = <X, Y, D, M, I, Z, SELECT>` tuple
3. **Validation** — structural consistency checks at construction time
4. **Example 1**: 1 Generator + 1 Processor (minimal coupling)
5. **Example 2**: 4 Generators + 1 Processor (paper case study)
6. **Example 3**: Hierarchical — two sub-coupled models feeding one Processor

---

## Step 1: Component Specification

**File**: `src/cadpya/modeling/component.py`
**Test file**: `tests/modeling/test_component.py`

### Design

A `ComponentSpec` describes everything needed to instantiate and initialize one sub-model inside a coupled model. The Coordinator (Phase 5) will use these specs to create **engines** — a Simulator for atomic models, or a sub-Coordinator for nested coupled models.

```python
from dataclasses import dataclass
from collections.abc import Callable

from cadpya.modeling.interval import Interval


@dataclass(frozen=True, slots=True)
class ComponentSpec[S, T, X, Y]:
    """Specification for one sub-model in a coupled model.

    Contains everything the Coordinator needs to create an engine
    (Simulator for atomic models, sub-Coordinator for coupled models).
    """

    model_factory: Callable[[Interval[S], Interval[T]], Any]
    initial_state: Interval[S]
    initial_elapsed: Interval[T]
```

- `model_factory`: the model class (e.g. `Generator`, `Processor`). Same callable the Simulator engine takes.
- `initial_state`: the `q_state` for engine `init()`.
- `initial_elapsed`: the `q_time` for engine `init()`.

### Why a separate class?

The Coordinator needs to iterate over all components and create an engine for each (Simulator for atomic, sub-Coordinator for coupled). Bundling factory + initial state into one object keeps the coupled model definition clean — the user declares components as a dict of `{name: ComponentSpec(...)}` rather than passing three separate dicts.

### Test cases

- Construct a `ComponentSpec` for Generator, Processor, Counter
- Verify immutability (frozen dataclass)
- Verify fields are accessible

---

## Step 2: Coupled Model Data Structure

**File**: `src/cadpya/modeling/coupled.py`
**Test file**: `tests/modeling/test_coupled.py`

### Design

A `CoupledModel` is a pure data structure describing the static coupling topology. It has no simulation behavior — that belongs to the Coordinator (Phase 5). It holds everything from the formal tuple `C = <X, Y, D, M, I, Z, SELECT>`.

Since we decided against ports (per `plans.md` decision #5), translation functions connect components by name, not by port. Each model has a single typed input and single typed output.

```python
@dataclass(frozen=True, slots=True)
class CoupledModel[T]:
    """IA-DEVS coupled model definition.

    Pure data structure describing the coupling topology.
    No simulation behavior — the Coordinator consumes this.

    Type parameters:
        T: base time type (shared across all components)
    """

    components: dict[str, ComponentSpec]
    influencers: dict[str, frozenset[str]]
    translations: dict[tuple[str, str], Callable[[Interval], Interval]]
    select: Callable[[frozenset[str]], str]
    zero_time: T
```

### Field descriptions

**`components: dict[str, ComponentSpec]`**

Maps component name → spec. Names are user-chosen strings (e.g. `"G1"`, `"P"`). The name `"self"` is reserved for the coupled model's own boundary.

**`influencers: dict[str, frozenset[str]]`**

Maps each component name to the set of components that influence it. Every component must have an entry, even if the set is empty.

- `I["P"] = frozenset({"G1", "G2", "G3", "G4"})` — all generators influence the processor
- `I["G1"] = frozenset()` — no one influences G1
- `I["self"] = frozenset({"P"})` — processor's output goes to the coupled model's output (EOC)

The key `"self"` in influencers means "which components produce external output". A component listed in `I["self"]` has an EOC translation.

**`translations: dict[tuple[str, str], Callable[[Interval], Interval]]`**

Maps `(source, destination)` → translation function. Three coupling types:

- IC: `("G1", "P")` → `Z_{G1,P}`: transforms Generator output to Processor input
- EOC: `("P", "self")` → `Z_{P,self}`: transforms Processor output to coupled model output
- EIC: `("self", "P")` → `Z_{self,P}`: transforms coupled model input to Processor input

Translation functions are `Callable[[Interval], Interval]` — they receive the source's output interval and return the destination's input interval. The type erasure is intentional: coupled models connect heterogeneous component types, so translations must bridge type differences.

**`select: Callable[[frozenset[str]], str]`**

Tie-breaking function. Given a non-empty set of imminent component names, returns the one that should execute first. Used by the Coordinator when the limit is punctual and multiple components are imminent.

**`zero_time: T`**

Shared zero time value, passed to each engine during init.

### Why `frozenset` for influencers?

Influencer sets are unordered and immutable after construction. `frozenset` enforces this and is hashable. We use `frozenset` in the public API and accept `set` or `frozenset` in the constructor for convenience.

### Why `dict` keys as `tuple[str, str]` for translations?

A single source can connect to multiple destinations (e.g. a generator could feed two processors). Using `(source, dest)` tuples as keys naturally supports this while being more explicit than nested dicts.

### Test cases

- Construct a minimal coupled model (1 component, no connections)
- Construct with IC, EOC, EIC translations
- Verify immutability
- Verify all fields accessible

---

## Step 3: Validation

**File**: `src/cadpya/modeling/coupled.py` (same file, validation in `__post_init__` or factory)
**Test file**: `tests/modeling/test_coupled.py` (validation tests)

### Validation rules (following Cadmia's `coupling_validator`)

1. **No empty components**: at least one component required
2. **All influencer references exist**: every name in influencer sets must be either a component name or `"self"`
3. **All components have influencer entries**: every component name must appear as a key in `influencers` (empty set is valid but must be explicitly registered)
4. **All translation endpoints exist**: for every `(source, dest)` in translations, both must be component names or `"self"`
5. **Translations match influencers**: for every `(source, dest)` in translations where `dest != "self"`, `source` must be in `influencers[dest]`
6. **Influencers have translations**: for every `(dest, sources)` in influencers, every `source` in `sources` must have a corresponding `(source, dest)` entry in translations. An influencer declaration without a translation function is an error — the Coordinator would have no way to route the output.
7. **`"self"` is not a component name**: reserved for the coupled model boundary
8. **SELECT is callable**: basic type check

### Error messages

Follow the Cadmia pattern — verbose, listing available components:

```
"Validation error: component 'G5' is listed as an influencer of 'P' but does not exist. Available components: ['G1', 'G2', 'G3', 'G4', 'P']"
```

### Implementation approach

Validation runs in `__post_init__` of the frozen dataclass. All errors are raised as `ValueError` with descriptive messages.

### Test cases

- Valid coupled model passes validation
- Missing influencer entry → ValueError
- Unknown component in influencer set → ValueError
- Translation referencing non-existent component → ValueError
- Translation without matching influencer → ValueError
- Influencer declared but no translation function for that pair → ValueError
- `"self"` used as component name → ValueError
- Empty components dict → ValueError

---

## Step 4: Example 1 — Generator-Processor (GP)

**File**: `tests/coupled_models/test_gp.py`

### Description

The simplest coupled model: 1 Generator feeding 1 Processor.

```
G1 --[Z_{G1,P}]--> P --[Z_{P,self}]--> (output)
```

### Components

- `"G"`: Generator with initial state `[0, 0]`, initial elapsed `[0, 0]`
- `"P"`: Processor with empty queue, initial elapsed `[0, 0]`

### Influencers

- `I["G"] = frozenset()` — no inputs
- `I["P"] = frozenset({"G"})` — Generator influences Processor
- `I["self"] = frozenset({"P"})` — Processor output goes external

### Translation functions

- `Z_{G,P}`: Generator output (Interval[Decimal]) → Processor input (Interval[int]). Maps the generator's decimal output interval to a job ID interval: `lambda y: Interval.closed(1, 1)` (always job 1).
- `Z_{P,self}`: Processor output → coupled model output. Identity: `lambda y: y`.

### SELECT

Not exercised in this example (only one active component at a time in the simplest case). Use a default: first alphabetically.

### Test cases

- Construct the GP coupled model — validation passes
- Verify component count is 2
- Verify influencer structure
- Verify translation functions produce correct output types
- Call `Z_{G,P}` with Generator's `OUTPUT_VALUE` → `Interval.closed(1, 1)`
- Call `Z_{P,self}` with `Interval.closed(1, 1)` → `Interval.closed(1, 1)`

### Note

These tests only verify the **data structure** — we cannot run the simulation yet (that's Phase 5 with the Coordinator). We test that the coupled model is correctly specified and that translation functions work in isolation.

---

## Step 5: Example 2 — Four Generators + Processor (4GP)

**File**: `tests/coupled_models/test_4gp.py`

### Description

The paper's case study: 4 Generators feeding 1 Processor. This is where branching becomes essential (Phase 5), but here we only define the data structure.

```
G1 --[Z_{G1,P}]--> P --[Z_{P,self}]--> (output)
G2 --[Z_{G2,P}]--/
G3 --[Z_{G3,P}]--/
G4 --[Z_{G4,P}]--/
```

### Components

- `"G1"`, `"G2"`, `"G3"`, `"G4"`: four Generator instances, all with `ZERO_STATE`, `ZERO_TIME`
- `"P"`: Processor with empty queue

### Influencers

- `I["G1"] = I["G2"] = I["G3"] = I["G4"] = frozenset()` — no inputs
- `I["P"] = frozenset({"G1", "G2", "G3", "G4"})` — all generators influence P
- `I["self"] = frozenset({"P"})` — processor output is external

### Translation functions

- `Z_{G1,P}`: `lambda y: Interval.closed(1, 1)` — job 1
- `Z_{G2,P}`: `lambda y: Interval.closed(2, 2)` — job 2
- `Z_{G3,P}`: `lambda y: Interval.closed(3, 3)` — job 3
- `Z_{G4,P}`: `lambda y: Interval.closed(4, 4)` — job 4
- `Z_{P,self}`: `lambda y: y` — identity

### SELECT

For this example, use alphabetical ordering (first in sorted order wins):

```python
def select_alphabetical(candidates: frozenset[str]) -> str:
    return sorted(candidates)[0]
```

### Test cases

- Construct the 4GP coupled model — validation passes
- Verify 5 components
- Verify P has 4 influencers
- Verify each translation maps to the correct job ID
- Verify SELECT picks "G1" from {"G1", "G2", "G3", "G4"}

---

## Step 6: Example 3 — Hierarchical Coupled Model

**File**: `tests/coupled_models/test_hierarchical.py`

### Description

Two sub-coupled models (each containing 2 generators) feeding one processor at the top level. This must be semantically equivalent to the flat 4GP model — same set of reachable trajectories.

```
Top-level coupled model:
  Left  = CoupledModel(G1, G2) --[Z_{Left,P}]--> P --[Z_{P,self}]--> (output)
  Right = CoupledModel(G3, G4) --[Z_{Right,P}]--/
```

Each sub-coupled model:
```
Left:
  G1 --[Z_{G1,self}]--> (output)
  G2 --[Z_{G2,self}]--> (output)

Right:
  G3 --[Z_{G3,self}]--> (output)
  G4 --[Z_{G4,self}]--> (output)
```

### Design question: how do sub-coupled models work?

A sub-coupled model is itself a `CoupledModel`. Its components are atomic models. Its external output (`"self"` in influencers) is what the parent coupled model sees.

The top-level coupled model's `ComponentSpec` for `"Left"` needs to reference the sub-coupled model. This means `ComponentSpec` can hold either:
1. An atomic model factory (for leaf models), or
2. A `CoupledModel` (for nested coupled models)

The Coordinator (Phase 5) will create the appropriate engine for each spec — a sub-Coordinator for nested `CoupledModel` specs, and a Simulator for atomic specs.

### ComponentSpec extension

```python
@dataclass(frozen=True, slots=True)
class ComponentSpec[S, T, X, Y]:
    model_factory: Callable[[Interval[S], Interval[T]], Any] | None
    initial_state: Interval[S] | None
    initial_elapsed: Interval[T] | None
    coupled_model: CoupledModel[T] | None = None
```

A `ComponentSpec` is either:
- **Atomic**: `model_factory`, `initial_state`, `initial_elapsed` are set; `coupled_model` is None
- **Coupled**: `coupled_model` is set; the others are None

We can provide factory methods for clarity:

```python
@classmethod
def atomic(cls, model_factory, initial_state, initial_elapsed) -> ComponentSpec: ...

@classmethod
def coupled(cls, coupled_model) -> ComponentSpec: ...
```

### Sub-coupled model: Left

- Components: `"G1"` (Generator), `"G2"` (Generator)
- `I["G1"] = I["G2"] = frozenset()`
- `I["self"] = frozenset({"G1", "G2"})` — both generators produce external output
- `Z_{G1,self}`: `lambda y: Interval.closed(1, 1)` — job 1
- `Z_{G2,self}`: `lambda y: Interval.closed(2, 2)` — job 2

### Sub-coupled model: Right

- Components: `"G3"` (Generator), `"G4"` (Generator)
- `I["G3"] = I["G4"] = frozenset()`
- `I["self"] = frozenset({"G3", "G4"})` — both generators produce external output
- `Z_{G3,self}`: `lambda y: Interval.closed(3, 3)` — job 3
- `Z_{G4,self}`: `lambda y: Interval.closed(4, 4)` — job 4

### Top-level coupled model

- Components: `"Left"` (CoupledModel), `"Right"` (CoupledModel), `"P"` (Processor)
- `I["Left"] = I["Right"] = frozenset()`
- `I["P"] = frozenset({"Left", "Right"})` — both sub-models feed P
- `I["self"] = frozenset({"P"})` — P output goes external
- `Z_{Left,P}`: identity `lambda y: y` — Left already produces job IDs
- `Z_{Right,P}`: identity `lambda y: y` — Right already produces job IDs
- `Z_{P,self}`: identity `lambda y: y`

### SELECT

Same alphabetical ordering at both levels.

### Test cases

- Construct Left sub-coupled model — validation passes
- Construct Right sub-coupled model — validation passes
- Construct top-level coupled model with nested specs — validation passes
- Verify hierarchical structure: top-level has 3 components, Left has 2, Right has 2
- Verify `ComponentSpec.coupled()` and `ComponentSpec.atomic()` factory methods

---

## File Summary

| File | Action |
|------|--------|
| `src/cadpya/modeling/component.py` | Create |
| `src/cadpya/modeling/coupled.py` | Create |
| `tests/modeling/test_component.py` | Create |
| `tests/modeling/test_coupled.py` | Create |
| `tests/coupled_models/__init__.py` | Create |
| `tests/coupled_models/test_gp.py` | Create |
| `tests/coupled_models/test_4gp.py` | Create |
| `tests/coupled_models/test_hierarchical.py` | Create |
| `CLAUDE.md` | Update with coupled model notes |

## Verification

After implementation:

1. `scripts/check-all.sh` passes (lint, format, mypy, pytest with 90%+ coverage)
2. All three coupled model examples construct and validate successfully
3. Translation functions produce correct output types when called in isolation
4. Validation rejects malformed coupled model definitions with clear error messages
5. Hierarchical nesting works (CoupledModel containing CoupledModel)

## Design Questions to Confirm During Implementation

1. **`ComponentSpec` generics**: The `ComponentSpec[S, T, X, Y]` has four type parameters, but components in a coupled model have different S/X/Y types (Generator has `Decimal` state, Processor has `ProcessorState`). The `components` dict in `CoupledModel` will need to hold heterogeneous specs. We may need `ComponentSpec` to be unparameterized or use a base type — or simply use `Any` in the dict type. Resolve during implementation.

2. **Translation function typing**: Translations bridge different types (`Interval[Decimal]` → `Interval[int]`). We type them as `Callable[[Interval], Interval]` (unparameterized Interval). mypy may complain. We may need `Callable[[Any], Any]` or a dedicated `Translation` type alias.

3. **Frozen dataclass with dict/frozenset fields**: A frozen dataclass doesn't deep-freeze its mutable fields. `dict` values are still mutable. We could use `MappingProxyType` for immutability, but that complicates construction. Keep `dict` for now and rely on convention (the Coordinator shouldn't mutate the coupled model).
