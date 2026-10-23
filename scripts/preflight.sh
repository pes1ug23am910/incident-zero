#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do
  case "$arg" in -h|--help|-Help)
    echo 'Usage: scripts/preflight.sh [--stack-root path] [--output-dir path] [--no-model]; read-only; skipped model fails'
    echo 'DOCKER_HOST is preserved; default is the platform Docker endpoint.'
    exit 0;;
  esac
done
source "$(dirname -- "${BASH_SOURCE[0]}")/_shell.sh"
incident_python -m scripts.preflight "$@"