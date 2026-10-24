#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do
  case "$arg" in -h|--help|-Help)
    echo 'Usage: scripts/ui.sh [--mode mock|real] [--reports-dir path] [--runs-dir path] [--port number]; INCIDENT_ZERO_PYTHON overrides interpreter'
    echo 'DOCKER_HOST is preserved; default is the platform Docker endpoint.'
    exit 0;;
  esac
done
source "$(dirname -- "${BASH_SOURCE[0]}")/_shell.sh"
incident_python -m scripts.operator ui "$@"