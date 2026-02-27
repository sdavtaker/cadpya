# Phase 1: Project Scaffolding — Detailed Plan

This document is the implementation guide for Phase 1. It contains every file to create, every configuration value, and exact content so implementation can proceed without ambiguity.

## Prerequisites

- Python 3.13+ installed (or 3.12 with awareness that some PEP 695 syntax may need adjustment)
- pipenv installed (`pip install --user pipenv` if not present)
- GitHub CLI (`gh`) authenticated

## Branch

Create branch `phase-1-scaffolding` from `main`.

## Deliverables

### 1. pyproject.toml

Single configuration file for package metadata and all tools.

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "cadpya"
version = "0.1.0"
description = "Python implementation of the IA-DEVS simulator"
license = {text = "BSD-2-Clause"}
requires-python = ">=3.13"
authors = [
    {name = "Damian Vicino", email = "sdavtaker@users.noreply.github.com"},
]
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=6",
    "ruff>=0.9",
    "mypy>=1.14",
]

[tool.setuptools.packages.find]
where = ["src"]

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

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true

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

### 2. Directory Structure

Create these directories and `__init__.py` files:

```
src/
  cadpya/
    __init__.py
    modeling/
      __init__.py
    engine/
      __init__.py
    basic_models/
      __init__.py
tests/
  __init__.py
  modeling/
    __init__.py
  engine/
    __init__.py
  basic_models/
    __init__.py
```

All `__init__.py` files are empty initially.

`src/cadpya/__init__.py` content:
```python
"""cadpya — Python implementation of the IA-DEVS simulator."""
```

All other `__init__.py` files are empty (zero bytes).

### 3. Pipfile

pipenv will generate this from `pipenv install`, but we should ensure it targets Python 3.13:

```
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
cadpya = {editable = true, extras = ["dev"], path = "."}

[dev-packages]

[requires]
python_version = "3.13"
```

Note: `Pipfile.lock` should be committed per pipenv recommendations (cross-platform caveats noted in .gitignore comments — we keep it committed by default).

### 4. Placeholder Test

A minimal test so pytest passes and coverage has something to measure:

`tests/test_smoke.py`:
```python
"""Smoke test to verify project setup."""

import cadpya


def test_package_is_importable() -> None:
    assert cadpya is not None
```

### 5. GitHub Actions CI

`.github/workflows/ci.yml`:

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

### 6. Convenience Scripts

Create a `scripts/` directory with thin shell wrappers. These give short memorable commands and ensure consistency.

`scripts/lint.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
pipenv run ruff check src/ tests/ "$@"
```

`scripts/fmt.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
pipenv run ruff format src/ tests/ "$@"
```

`scripts/typecheck.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
pipenv run mypy src/ "$@"
```

`scripts/test.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
pipenv run pytest "$@"
```

`scripts/check-all.sh` (runs everything CI runs, in order):
```bash
#!/usr/bin/env bash
set -euo pipefail
echo "=== ruff check ==="
pipenv run ruff check src/ tests/
echo "=== ruff format check ==="
pipenv run ruff format --check src/ tests/
echo "=== mypy ==="
pipenv run mypy src/
echo "=== pytest ==="
pipenv run pytest
echo "=== all checks passed ==="
```

All scripts must be `chmod +x`.

### 7. Update CLAUDE.md

Replace the current CLAUDE.md with working commands and project context:

```markdown
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

## Git Workflow

- Create a feature branch for every change
- Open a PR for review — never push directly to main
- Use `gh` CLI for GitHub operations, not raw git push
```

### 8. Update .gitignore

The existing .gitignore already covers Python artifacts. Verify these entries are present (they should be from the standard Python gitignore):

- `__pycache__/` — yes
- `*.py[codz]` — yes
- `*.egg-info/` — yes
- `.env` — yes
- `Pipfile.lock` — currently commented out, we should **uncomment** it to keep it tracked (or just ensure it's not ignored)

Check: the `.gitignore` has `#Pipfile.lock` (commented out), meaning Pipfile.lock IS tracked. This is correct — no change needed.

## Verification Checklist

After all files are created, run these commands and confirm they all pass:

1. `pipenv install -e ".[dev]"` — installs without errors
2. `scripts/lint.sh` — no lint errors
3. `scripts/fmt.sh --check` — no formatting issues (pass `--check` to verify)
4. `scripts/typecheck.sh` — no type errors
5. `scripts/test.sh` — test passes, coverage reported
6. `scripts/check-all.sh` — everything green

## Files Changed Summary

| File | Action |
|------|--------|
| `pyproject.toml` | Create |
| `src/cadpya/__init__.py` | Create |
| `src/cadpya/modeling/__init__.py` | Create |
| `src/cadpya/engine/__init__.py` | Create |
| `src/cadpya/basic_models/__init__.py` | Create |
| `tests/__init__.py` | Create |
| `tests/modeling/__init__.py` | Create |
| `tests/engine/__init__.py` | Create |
| `tests/basic_models/__init__.py` | Create |
| `tests/test_smoke.py` | Create |
| `.github/workflows/ci.yml` | Create |
| `scripts/lint.sh` | Create |
| `scripts/fmt.sh` | Create |
| `scripts/typecheck.sh` | Create |
| `scripts/test.sh` | Create |
| `scripts/check-all.sh` | Create |
| `CLAUDE.md` | Update |
| `Pipfile` | Generated by pipenv (committed) |
| `Pipfile.lock` | Generated by pipenv (committed) |

## Notes

- The coverage threshold is 90%. With only a smoke test and a single `__init__.py` with a docstring, this should pass trivially. As source code grows, tests must keep pace.
- The `--cov-fail-under=90` in pytest addopts means CI and local `scripts/test.sh` both enforce the threshold identically.
- If the local Python is 3.12 (not 3.13), we can still proceed — the key PEP 695 features (type aliases, generic syntax) were introduced in 3.12. We target 3.13 in config but 3.12 will work for Phase 1. Syntax requiring 3.13 specifically will appear in later phases.
