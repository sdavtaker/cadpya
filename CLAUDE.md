# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cadpya** is a Python implementation of the IA-DEVS simulator (Interval-Approximated Discrete Event Systems). Licensed under BSD 2-Clause (Damian Vicino, 2026).

See `reference.md` for the full technical reference and `plans.md` for the implementation roadmap.

## Commands

All commands use pipenv. Never use pip or python directly.

```bash
# Setup
pipenv install -e ".[dev]"

# Development
scripts/test.sh                  # run tests with coverage
scripts/lint.sh                  # ruff linting
scripts/fmt.sh                   # ruff formatting
scripts/typecheck.sh             # mypy strict type checking
scripts/check-all.sh             # run all checks (same as CI)

# Single test
pipenv run pytest tests/modeling/test_interval.py::test_name -x

# Quick test without coverage
pipenv run pytest --no-cov -x
```

## Conventions

- Python 3.13+, latest idioms (PEP 695 generics, match, Protocol, dataclasses with slots)
- Zero runtime dependencies — stdlib only
- `src/` layout: source in `src/cadpya/`, tests in `tests/`
- 90% test coverage threshold enforced by CI
- See `dev-guide.md` for full coding patterns and tool configuration

## Architecture Notes

### Core Types (`src/cadpya/modeling/`)

- **Decimal**: Thin wrapper around `decimal.Decimal` (stdlib) with fixed scale. Strict construction (rejects non-zero digits beyond scale). Cross-scale comparison via `as_lower_bound()`/`as_upper_bound()`. All arithmetic enforces same-scale.
- **Interval[T]**: Generic over any totally-ordered T. Supports open/closed bounds, +/-infinity, Minkowski addition, interval subtraction, subset, intersection. Empty interval represents passiveness. Immutable with `__slots__`.

### Atomic Models (`src/cadpya/basic_models/`)

All models follow the same pattern:
- Constructor: `__init__(self, initial_state, initial_time)` — called by simulator `init()`
- Transition functions: `internal_transition()`, `external_transition(elapsed, x)` — mutate `_state`
- `output()` → `Interval[Output]`, `time_advance()` → `Interval[Time] | None` (None = passive)
- Type aliases via PEP 695 `type` statement: `type State = ...`, `type Time = ...`, etc.
- Models: Generator (scalar state, periodic output), Processor (tocj + job queue), Counter (phase enum + count)

### Engine (`src/cadpya/engine/`)

- **AtomicModel Protocol**: `@runtime_checkable` structural typing interface (`Protocol[S, T, X, Y]`). Models satisfy it without inheritance. Methods: `internal_transition()`, `external_transition(elapsed, x)`, `output()`, `time_advance()`, `state_interval` property.
- **Simulator**: Algorithm 1 from VWD21. Wraps one atomic model. `init(q_state, q_time, t)` constructs the model and sets `t_last`/`t_next`. `star_function(t)` handles internal events (validates `t ⊆ t_next`). `x_function(x, t)` handles external events with elapsed-time computation (confluent case clamps lower bound to 0 when `t` intersects `t_last`).

### Coupled Models (`src/cadpya/modeling/`)

- **ComponentSpec**: Frozen dataclass describing one sub-model. Either atomic (`model_factory` + `initial_state` + `initial_elapsed`) or coupled (nested `CoupledModel`). Factory methods: `ComponentSpec.atomic()`, `ComponentSpec.coupled()`.
- **CoupledModel[T]**: Pure data structure for coupling topology `C = <X, Y, D, M, I, Z, SELECT>`. Components dict, influencers (frozenset per component), translations keyed by `(source, dest)` tuples, SELECT callable, zero_time. `"self"` reserved for coupled model boundary (EOC/EIC). Validates referential integrity at construction: all influencer references exist, all components have entries, translations match influencers bidirectionally.

## Git Workflow

- Create a feature branch for every change
- Open a PR for review — never push directly to main
- Use `gh` CLI for GitHub operations, not raw git push
