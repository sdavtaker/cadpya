# cadpya Development Guide

## Python Version

**Python 3.13+** required. We use the latest language features without hesitation:

- `type` statement for type aliases (PEP 695)
- Generic syntax with `class Foo[T]:` (PEP 695)
- `match` statements for pattern matching (PEP 634)
- `dataclasses` with `slots=True` and `kw_only=True`
- `Self` type from `typing` (PEP 673)
- `override` decorator from `typing` (PEP 698)
- Union types with `X | Y` syntax
- `Protocol` for structural subtyping

## Project Layout

```
cadpya/
├── pyproject.toml
├── src/
│   └── cadpya/
│       ├── __init__.py
│       ├── modeling/          # Core data types (interval, decimal)
│       ├── engine/            # Simulator, Coordinator, Root Coordinator
│       └── basic_models/      # Example IA-DEVS atomic and coupled models
├── tests/
│   ├── modeling/
│   ├── engine/
│   └── basic_models/
├── reference.md
├── plans.md
└── dev-guide.md
```

We use the `src/` layout to prevent accidental imports of the source tree root.

## Build & Package Management

**pipenv** for all environment and dependency management. Never use `pip` or `python` directly.

**pyproject.toml** as the single configuration file for package metadata and tool settings. No setup.py, setup.cfg, requirements.txt, or tool-specific config files.

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "cadpya"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=6",
    "ruff>=0.9",
    "mypy>=1.14",
]
```

Common commands:
```bash
pipenv install -e ".[dev]"     # install project + dev dependencies
pipenv run pytest              # run tests
pipenv run ruff check src/     # lint
pipenv run mypy src/           # type check
pipenv shell                   # activate virtualenv for interactive work
```

## Dependencies

### Runtime: Zero

cadpya has **no runtime dependencies**. The core library (intervals, decimals, simulator engine) uses only the Python standard library. This is deliberate — a simulation framework should not impose dependency choices on its users.

### Development

| Tool | Purpose |
|------|---------|
| **pytest** | Testing framework |
| **pytest-cov** | Coverage reporting |
| **ruff** | Linting and formatting (replaces flake8, isort, black) |
| **mypy** | Static type checking (strict mode) |

No other dev dependencies unless a concrete need arises.

## Linting & Formatting: ruff

Single tool for both linting and formatting. Configuration in pyproject.toml:

```toml
[tool.ruff]
target-version = "py313"
line-length = 99

[tool.ruff.lint]
select = [
    "E", "W",       # pycodestyle
    "F",             # pyflakes
    "I",             # isort
    "N",             # pep8-naming
    "UP",            # pyupgrade
    "B",             # flake8-bugbear
    "SIM",           # flake8-simplify
    "TCH",           # flake8-type-checking
    "RUF",           # ruff-specific
    "PT",            # flake8-pytest-style
    "C4",            # flake8-comprehensions
    "PIE",           # flake8-pie
    "RET",           # flake8-return
]
```

Commands:
```bash
ruff check src/ tests/        # lint
ruff format src/ tests/        # format
ruff check --fix src/ tests/   # auto-fix
```

## Type Checking: mypy

Strict mode. Configuration in pyproject.toml:

```toml
[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
```

Command:
```bash
mypy src/
```

## Testing: pytest + coverage

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "-v --tb=short --cov=cadpya --cov-report=term-missing --cov-fail-under=90"

[tool.coverage.run]
source = ["src/cadpya"]
branch = true

[tool.coverage.report]
show_missing = true
fail_under = 90
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "@overload",
]
```

**Coverage target: 90%+**. This project involves complex interval arithmetic and branching simulation logic — high coverage is mandatory to catch regressions as we iterate and refactor.

Commands:
```bash
pipenv run pytest                          # run all tests (with coverage)
pipenv run pytest tests/modeling/          # run tests for a module
pipenv run pytest tests/modeling/test_interval.py::test_closed_addition  # single test
pipenv run pytest -x                       # stop on first failure
pipenv run pytest -k "interval"            # run tests matching pattern
pipenv run pytest --no-cov                 # skip coverage (faster iteration)
```

### Test organization

Mirror the source layout under `tests/`. One test file per source module. Test names describe the behavior, not the method:

```python
# Good
def test_closed_interval_addition_produces_closed_result(): ...
def test_empty_interval_is_identity_for_union(): ...
def test_generator_time_advance_returns_period_minus_state(): ...

# Bad
def test_add(): ...
def test_interval_1(): ...
```

## CI: GitHub Actions

A single workflow file `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install pipenv
      - run: pipenv install -e ".[dev]"
      - run: pipenv run ruff check src/ tests/
      - run: pipenv run ruff format --check src/ tests/
      - run: pipenv run mypy src/
      - run: pipenv run pytest
```

Single job, fast feedback. No matrix builds or separate lint/test jobs unless the test suite grows large. The pytest step enforces the 90% coverage threshold — CI fails if coverage drops below it.

## Coding Patterns

### Dataclasses for value types

Use `@dataclass(frozen=True, slots=True)` for immutable value types (intervals, decimal values, simulation messages). Frozen dataclasses are hashable by default and prevent accidental mutation.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Interval[T]:
    lower: T
    upper: T
    lower_closed: bool
    upper_closed: bool
    lower_inf: int = 0   # -1, 0, +1
    upper_inf: int = 0
```

### Protocol for model contracts

Use `Protocol` (structural subtyping) for the atomic model interface. This allows models to be plain classes without inheriting from a base — matching C++ concepts semantics.

```python
from typing import Protocol

class AtomicModel[S, T, X, Y](Protocol):
    def internal_transition(self) -> None: ...
    def external_transition(self, elapsed: Interval[T], x: Interval[X]) -> None: ...
    def output(self) -> Interval[Y]: ...
    def time_advance(self) -> Interval[T] | None: ...
    @property
    def state_interval(self) -> Interval[S]: ...
```

`None` return from `time_advance` means passive (empty set in the formalism).

### `__slots__` everywhere for engine internals

Simulator, Coordinator, and engine classes should use `__slots__` for memory efficiency — critical when cloning state for BFS branching.

### `match` for dispatch in transition functions

Pattern matching is natural for models with discrete phases:

```python
def internal_transition(self) -> None:
    match (self._state.lower.phase, self._state.upper.phase):
        case (Phase.OUTPUT, Phase.OUTPUT):
            self._state = Interval.closed(State(Phase.PASSIVE, 0), State(Phase.PASSIVE, 0))
        case (Phase.PASSIVE, Phase.OUTPUT):
            ...
```

### Factory methods over constructors for intervals

Follow the Cadmia pattern — `Interval.closed(lo, hi)`, `Interval.open(lo, hi)`, `Interval.empty()` etc. Never call `__init__` directly for intervals.

### `__eq__`, `__lt__`, `__le__` via `@functools.total_ordering` or manual `__eq__`/`__lt__`

State types that go inside intervals need total ordering. Use `@total_ordering` for simple cases, explicit `__lt__` for composite states where comparison order matters (e.g., Processor: compare tocj first, then queue).

Alternatively, for simple state structs, leverage `dataclass(order=True)` which generates comparison methods from field order.

### Explicit `__deepcopy__` for simulation state

BFS branching requires deep-copying the entire engine hierarchy. Implement `__deepcopy__` on Simulator and Coordinator to control what gets copied (avoid copying immutable model definitions, only copy mutable state).

### No inheritance hierarchies for models

Models are plain classes satisfying a Protocol. No `AbstractAtomicModel` base class. This keeps models lightweight and avoids the fragile base class problem.

### Error messages reference the formalism

When raising exceptions in engine code, reference the algorithm and invariant:

```python
if not t.is_subset_of(self._t_next):
    raise SimulationError(
        f"Simulator.*-function invariant violated: t={t} is not a subset of t_next={self._t_next}"
    )
```

### String representations for debugging

All value types implement `__repr__` with round-trippable output and `__str__` with human-readable output:

```python
repr: Interval.closed(Decimal3(997), Decimal3(1005))
str:  [0.997, 1.005]
```

## Simulation Output Format

The simulator produces a structured log where each line is a JSON object. This enables:
- Querying how a particular state was reached (trace back via previous step references)
- Constructing a visual graph of the simulation run
- Parsing with standard tools (jq, pandas, etc.)

Each log entry contains:

| Field | Description |
|-------|-------------|
| `step` | Monotonic step counter (unique per branch) |
| `branch` | Branch identifier |
| `parent_step` | Step that led to this one (for graph construction) |
| `time` | Global simulation time interval |
| `component` | Name of the model being acted on |
| `operation` | One of: `init`, `internal`, `external`, `output`, `fork` |
| `state` | State interval after the operation |
| `output` | Output interval (for `output` and `internal` operations) |
| `input` | Input interval (for `external` operations) |
| `t_next` | Next scheduled event time interval |

Example:
```json
{"step": 0, "branch": 0, "parent_step": null, "time": "[0, 0]", "component": "G1", "operation": "init", "state": "[0, 0]", "t_next": "[0.997, 1.005]"}
{"step": 1, "branch": 0, "parent_step": 0, "time": "[0.997, 1.005]", "component": "G1", "operation": "internal", "state": "[0, 0]", "output": "[1.997, 2.003]", "t_next": "[1.994, 2.010]"}
{"step": 2, "branch": 0, "parent_step": 1, "time": "[0.997, 1.005]", "component": "P", "operation": "external", "state": "...", "input": "[1, 1]", "t_next": "[1.247, 1.255]"}
```

The `branch` + `parent_step` fields form a tree structure that can be visualized as a DAG showing all explored simulation paths.

## Naming Conventions

- Modules and packages: `snake_case`
- Classes: `PascalCase`
- Functions and methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Type variables: single uppercase letter or short PascalCase (`T`, `S`, `StateT`)
- Private members: single leading underscore `_state`
- No double underscores except for dunder methods

Map formalism names to code names:
- Delta_int → `internal_transition`
- Delta_ext → `external_transition`
- Lambda → `output`
- TA → `time_advance`
- *-function → `star_function`
- x-function → `x_function`
- BoundTs → `bound_ts`
- Z^AI → translation functions (passed as callables)
- SELECT → `select` (passed as callable)
