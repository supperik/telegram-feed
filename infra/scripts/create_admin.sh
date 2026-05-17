#!/usr/bin/env bash
# Thin wrapper: runs the interactive create_admin.py inside the api
# container, with stdin attached so prompts work.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

exec docker compose exec -i api python -m scripts.create_admin "$@"
