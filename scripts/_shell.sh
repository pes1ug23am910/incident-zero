#!/usr/bin/env bash
# Source from an entry point. Resolve the checkout even when called elsewhere.
set -euo pipefail
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
incident_python() {
  local py="${INCIDENT_ZERO_PYTHON:-}"
  if [[ -z "$py" ]]; then
    if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then py="$REPO_ROOT/.venv/bin/python"
    elif [[ -f "$REPO_ROOT/.venv/Scripts/python.exe" ]]; then py="$REPO_ROOT/.venv/Scripts/python.exe"
    else echo 'Create .venv and install .[test] as documented in README.' >&2; return 1; fi
  fi
  cd -- "$REPO_ROOT"
  "$py" "$@"
}
