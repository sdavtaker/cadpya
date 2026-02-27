#!/usr/bin/env bash
set -euo pipefail
pipenv run ruff check src/ tests/ "$@"
