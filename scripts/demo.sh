#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do
  case "$arg" in -h|--help|-Help)
    echo 'Usage: scripts/demo.sh [--live] [--incident name] [--svc name] [--report-id id] [--operator name] [--load-users 20] [--rejected-report path] [--browser-approval]; default preview'
    echo 'DOCKER_HOST is preserved; default is the platform Docker endpoint.'
    exit 0;;
  esac
done
source "$(dirname -- "${BASH_SOURCE[0]}")/_shell.sh"
incident_python -m scripts.operator demo "$@"