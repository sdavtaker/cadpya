#!/usr/bin/env bash
set -euo pipefail
pipenv run ruff format src/ tests/ "$@"
