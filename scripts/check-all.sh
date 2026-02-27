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
