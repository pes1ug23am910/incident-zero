"""Command-line access to the read-only telemetry package."""

import argparse
import json

from . import get_metrics, get_traces, get_logs, get_container_health, get_deploy_history, health_table, list_services
from .queries import QUERIES
from .resolve import resolve, EvidenceNotFound


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="tool", required=True)
    metrics = commands.add_parser("get_metrics", aliases=["metrics"])
    metrics.add_argument("promql", help="PromQL expression or named query: " + ", ".join(QUERIES))
    metrics.add_argument("--lookback-s", type=int, default=300)
    metrics.add_argument("--step-s", type=float, default=15)
    traces = commands.add_parser("get_traces", aliases=["traces"])
    traces.add_argument("service")
    traces.add_argument("--lookback-s", type=int, default=300)
    traces.add_argument("--limit", type=int, default=20)
    traces.add_argument("--all", dest="errors_only", action="store_false")
    traces.add_argument("--operation")
    logs = commands.add_parser("get_logs", aliases=["logs"])
    logs.add_argument("service")
    logs.add_argument("--pattern")
    logs.add_argument("--lookback-s", type=int, default=300)
    logs.add_argument("--severity-min", default="WARN")
    logs.add_argument("--limit", type=int, default=50)
    containers = commands.add_parser("get_container_health", aliases=["containers"])
    containers.add_argument("names", nargs="*")
    deploy = commands.add_parser("get_deploy_history", aliases=["deploys"])
    deploy.add_argument("--lookback-s", type=int, default=3600)
    health = commands.add_parser("health_table", aliases=["health"])
    health.add_argument("--lookback-s", type=int, default=120)
    commands.add_parser("list_services", aliases=["services"])
    evidence = commands.add_parser("resolve")
    evidence.add_argument("evidence_id")
    commands.add_parser("queries")
    values = vars(parser.parse_args(argv))
    name = values.pop("tool")
    functions = {"get_metrics": get_metrics, "metrics": get_metrics, "get_traces": get_traces, "traces": get_traces,
                 "get_logs": get_logs, "logs": get_logs, "get_container_health": get_container_health,
                 "containers": get_container_health, "get_deploy_history": get_deploy_history, "deploys": get_deploy_history,
                 "health_table": health_table, "health": health_table, "list_services": list_services, "services": list_services,
                 "resolve": resolve}
    if name == "queries":
        print(json.dumps(QUERIES, indent=2))
        return 0
    if "names" in values and not values["names"]:
        values["names"] = None
    try:
        result = functions[name](**values)
    except EvidenceNotFound as exc:
        result = {"error": str(exc)}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
