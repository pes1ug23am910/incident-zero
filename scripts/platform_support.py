"""Shared shell support; never overrides the operator's Docker endpoint."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def docker_host(env=None, platform=None):
    env = os.environ if env is None else env
    return env.get("DOCKER_HOST") or (
        "npipe:////./pipe/docker_engine" if (platform or sys.platform) == "win32"
        else "unix:///var/run/docker.sock")


def environment():
    os.environ.setdefault("DOCKER_HOST", docker_host())
    os.environ.setdefault("DEMO_VERSION", "2.0.2")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def run_module(module, *args, **kwargs):
    return subprocess.call([sys.executable, "-m", module, *map(str, args)], cwd=ROOT, **kwargs)


def stamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def table(rows):
    return "| Check | Result | Detail |\n|---|---|---|\n" + "\n".join(
        "| " + " | ".join(str(v).replace("|", "/").replace("\n", " ") for v in row) + " |"
        for row in rows) + "\n"
