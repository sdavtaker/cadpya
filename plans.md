# cadpya Implementation Plans

This document tracks the planning and implementation steps for the cadpya IA-DEVS simulator.

## Status: Planning Phase

We are currently in the planning phase. No implementation should begin until this plan is reviewed and approved.

## Resolved Decisions

1. **FORK/Branching strategy**: BFS execution queue. A queue holds pending simulation steps. Single next-step → append to queue. Multiple next-steps → clone the full simulation state for each branch and enqueue all. This ensures breadth-first exploration (DFS would be infinite). Memory optimization (DB, caches, deduplication) deferred to later.

2. **Computable functions only**: Modelers implement the capital-letter functions directly (Delta_int, Delta_ext, Lambda, TA) with interval bounding already built in. The paper's decomposition into small-letter functions + separate bound functions is for theoretical justification only. There is no runtime composition of `delta_int` + `S_lowerbound`. The small-letter functions may not be individually computable.

3. **State representation**: Follows from decision 2 — since modelers write the capital-letter functions directly, they handle their own composite state types and bounding logic inside those functions. The framework only needs to know that state is an opaque interval-like object that the model's functions consume and produce.

4. **Branch merging**: Deferred. Not in initial implementation.

5. **No ports / no multiports**: Ports and multiports are out of scope. The interaction between port-based coupling simplification (EIC/IC/EOC) and uncertainty intervals is not yet researched. We use Z translation functions directly, with single typed input/output per model.

## Open Questions

_None at this time._

## Implementation Approach: Models First

We build **example models before framework abstractions**. This lets us discover the right API by writing real user-facing code first, then extract the patterns into protocols and engine components. Each phase builds the minimum supporting infrastructure needed for that phase's models.

## Implementation Steps

### Phase 1: Project Scaffolding
- [ ] pyproject.toml with package metadata, pytest, ruff, mypy config (per dev-guide.md)
- [ ] `src/cadpya/` package structure with `modeling/`, `engine/`, `basic_models/` subpackages
- [ ] `tests/` directory mirroring source layout
- [ ] GitHub Actions CI workflow (ruff check, ruff format --check, mypy, pytest with coverage)
- [ ] Convenience scripts and/or Claude Code skills for running build, lint, format, type-check, and tests — so these are always at hand during development without remembering exact commands
- [ ] Verify: `pipenv install -e ".[dev]"`, `pipenv run pytest`, `pipenv run ruff check`, `pipenv run mypy src/` all pass on empty project
- [ ] Update CLAUDE.md with the working commands

### Phase 2: Example Atomic Models + Supporting Types
Build the three example atomic models from the paper/Cadmia. Implement `Decimal` and `Interval` types as needed to support them — not as a separate big-bang library phase, but driven by what the models actually require.

- [ ] **Decimal fixed-point type** (`src/cadpya/modeling/decimal.py`): parameterized by scale (e.g., scale=3 → 1ms resolution). Arithmetic (+, -), comparison, repr/str. Built as needed by models.
- [ ] **Interval type** (`src/cadpya/modeling/interval.py`): generic `Interval[T]` for any ordered T. Factory methods (closed, open, left_open, right_open, empty), infinity support, Minkowski addition (+), interval subtraction (-), is_subset_of, intersects, is_empty. Built incrementally as models demand operations.
- [ ] **Generator model** (`src/cadpya/basic_models/generator.py`): scalar state (Decimal), fixed output interval, periodic time advance with uncertainty. Simplest model — drives initial Interval and Decimal API.
- [ ] **Processor model** (`src/cadpya/basic_models/processor.py`): composite state (tocj: Decimal + qj: deque of job IDs). Exercises interval over composite ordered types, queue manipulation under uncertainty.
- [ ] **Counter model** (`src/cadpya/basic_models/counter.py`): discrete phase (passive/output) + count. Exercises interval over enum-like discrete states, phase-dependent time advance.
- [ ] Tests for each model's transition functions (internal, external, output, time_advance) in isolation — calling them directly, not through a simulator.
- [ ] Tests for Decimal and Interval covering all operations exercised by the models.

**Goal of this phase**: settle on a user-facing API for atomic models. By the end, we should know exactly what the Protocol will look like, because we've written three real models against it.

### Phase 3: Atomic Model Protocol + Simulator
Now extract the common pattern from Phase 2 models into a formal Protocol, and build the Simulator engine.

- [ ] **Atomic model Protocol** (`src/cadpya/engine/protocol.py`): structural typing interface extracted from the three models. No base class — models are plain classes satisfying the Protocol.
- [ ] **Simulator** (`src/cadpya/engine/simulator.py`): init, star_function, x_function (Algorithm 1 from paper). Holds model instance + t_last + t_next intervals.
- [ ] **Verify**: run Generator, Processor, Counter through the Simulator with manual init + step calls. Confirm state/time values match paper Tables.
- [ ] Simulator unit tests: invariant checking (t subset of t_next), state progression, passive detection.

### Phase 4: Example Coupled Models + Supporting Types
Write coupled model examples before formalizing the Coordinator. Discover the coupling API.

- [ ] **Coupled model example 1**: 1 Generator + 1 Processor. Minimal coupling with a single Z translation function.
- [ ] **Coupled model example 2**: 4 Generators + 1 Processor (the paper's case study). Four Z translations, SELECT function.
- [ ] **Coupled model example 3**: Multi-level hierarchy. Two Generators in one coupled model, two Generators in another coupled model, both coupled models connected to the Processor in a top-level coupled model. This must produce equivalent simulation behavior to example 2 (same model semantics described differently via hierarchy), validating that hierarchical coupling works correctly.
- [ ] Define the coupled model data structure (D, M, influencers, Z translations, SELECT) based on what these examples need.

**Goal of this phase**: settle on how users define coupled models and their couplings, including hierarchical nesting.

### Phase 5: Coordinator + Root Coordinator + Branching
Build the engine for coupled models, the simulation main loop, and the BFS branching mechanism together — the Coordinator cannot be verified without branching since the *-function produces forks.

- [ ] **Coordinator** (`src/cadpya/engine/coordinator.py`): init, star_function, x_function, route (Algorithms 2-3 from paper). Bounding logic coupled to Z translation functions (not standalone BoundTs).
- [ ] **Root Coordinator** (`src/cadpya/engine/root_coordinator.py`): main simulation loop (Algorithm 4 from paper).
- [ ] **BFS execution queue**: queue of pending simulation steps, state cloning on branch points.
- [ ] **State cloning mechanism**: deep copy of full engine hierarchy including all model state.
- [ ] **Structured log output**: JSON-lines format per dev-guide.md / reference.md Section 10. Each step records operation, state, time, component, branch, parent_step. Fork events logged.
- [ ] Coordinator unit tests with simple coupled systems.

### Phase 6: End-to-End Validation
- [ ] Full simulation run of paper case study (4 generators + 1 processor) with branching
- [ ] Verify initialization matches Table 1 from paper
- [ ] Verify first simulation steps match Tables 2-5 from paper
- [ ] Verify branch count matches paper expectations (24 branches after first wave)
- [ ] Run hierarchical coupled model (example 3) and verify equivalent behavior to flat model (example 2)
- [ ] Verify structured log can reconstruct the simulation tree
- [ ] Performance baseline on the case study
