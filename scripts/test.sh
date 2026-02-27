#!/usr/bin/env bash
set -euo pipefail
pipenv run pytest "$@"
