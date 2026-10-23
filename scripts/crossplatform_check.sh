#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do
  case "$arg" in -h|--help|-Help)
    echo 'Usage: scripts/crossplatform_check.sh [--output-dir path] [--print-command]; disposable python:3.11, read-only repository'
    echo 'DOCKER_HOST is preserved; default is the platform Docker endpoint.'
    exit 0;;
  esac
done
source "$(dirname -- "${BASH_SOURCE[0]}")/_shell.sh"
incident_python -m scripts.crossplatform_check "$@"