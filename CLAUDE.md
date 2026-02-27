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
