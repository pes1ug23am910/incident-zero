"""Container state and resource reads, scoped to the demo Compose project."""

from concurrent.futures import ThreadPoolExecutor
import contextvars
import json
import os
import re
import subprocess

from .common import bounded, docker, envelope, window, BackendError

INSPECT_FORMAT = ('{"Name":{{json .Name}},"State":{{json .State}},'
                  '"RestartCount":{{json .RestartCount}},"Created":{{json .Created}},'
                  '"NanoCpus":{{json .HostConfig.NanoCpus}},"Memory":{{json .HostConfig.Memory}}}')


def container_names():
    project = os.environ.get("DEMO_PROJECT", "opentelemetry-demo")
    return docker("ps", "-a", "--filter", f"label=com.docker.compose.project={project}",
                  "--format", "{{.Names}}").splitlines()


def inspect_rows(names=None):
    available = container_names()
    selected = available if names is None else list(names)
    if any(n not in available for n in selected):
        raise ValueError("Container names must belong to the demo Compose project")
    if not selected:
        return []
    return [json.loads(line) for line in docker("inspect", "--format", INSPECT_FORMAT, *selected).splitlines()]


def memory_mb(value):
    match = re.match(r"\s*([\d.]+)\s*([A-Za-z]+)", value)
    if not match:
        return None
    units = {"B": 1e-6, "kB": 1e-3, "KB": 1e-3, "KiB": 1024 / 1e6,
             "MB": 1, "MiB": 1048576 / 1e6, "GB": 1000, "GiB": 1073741824 / 1e6}
    unit = units.get(match[2])
    return float(match[1]) * unit if unit is not None else None


def evidence_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def health_row(item, stats=None):
    state = item["State"]
    stats = stats or {}
    return {"name": item["Name"].lstrip("/"), "Status": state["Status"],
            "RestartCount": item["RestartCount"], "OOMKilled": state.get("OOMKilled", False),
            "StartedAt": state.get("StartedAt"), "Created": item["Created"],
            "NanoCpus": item["NanoCpus"], "Memory": item["Memory"],
            "health": state.get("Health", {}).get("Status"),
            "cpu_percent": float(stats.get("CPUPerc", "0%").rstrip("%")) if stats else None,
            "memory_mb": memory_mb(stats.get("MemUsage", ""))}


@bounded("docker")
def get_container_health(names=None):
    selected = container_names()
    if names is not None:
        if isinstance(names, str):
            names = [names]
        if any(n not in selected for n in names):
            raise ValueError("Container names must belong to the demo Compose project")
        selected = list(names)
    if not selected:
        return envelope("get_container_health", "docker", "inspect + stats", window(), [],
                        warning="No containers found for the selected Compose project")
    # Stats sampling and inspection run together, so status never waits on a second sample.
    def read_inspect():
        return [json.loads(line) for line in docker("inspect", "--format", INSPECT_FORMAT, *selected).splitlines()]
    def read_stats():
        return {row["Name"]: row for row in (json.loads(line) for line in
                docker("stats", "--no-stream", "--format", "{{json .}}", *selected).splitlines())}
    warnings = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_inspect = pool.submit(contextvars.copy_context().run, read_inspect)
        future_stats = pool.submit(contextvars.copy_context().run, read_stats)
        inspected = future_inspect.result()
        try:
            stats = future_stats.result()
        except (ValueError, OSError, TimeoutError, subprocess.SubprocessError) as exc:
            stats = {}
            warnings.append("Live resource sample unavailable: " + str(exc)[:200])
    rows = [health_row(item, stats.get(item["Name"].lstrip("/"))) for item in inspected]
    ids = [f'container:{row["name"]}:{field}={evidence_value(row[field])}' for row in rows
           for field in ("Status", "RestartCount", "OOMKilled", "StartedAt", "NanoCpus", "Memory")]
    return envelope("get_container_health", "docker", "inspect + stats", window(), rows, ids,
                    **({"warnings": warnings} if warnings else {}))
