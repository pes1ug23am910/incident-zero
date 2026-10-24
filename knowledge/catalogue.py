"""Reproduce a sanitized catalogue from Compose configuration without deployment.

Only service names and depends_on edges are retained from Compose output.
Environment values, mounts, images, commands and settings are never stored.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import yaml

from tools.redact import is_sensitive

PURPOSES = {
    "accounting": ("Consumes order events for accounting processing.", "core"),
    "ad": ("Supplies advertisements for storefront pages.", "auxiliary"),
    "cart": ("Stores and retrieves shopping carts through the cache.", "critical"),
    "checkout": ("Coordinates cart, prices, payment, shipping and order completion.", "critical"),
    "currency": ("Converts prices between supported currencies.", "core"),
    "email": ("Sends order confirmation messages.", "auxiliary"),
    "fraud-detection": ("Consumes order events for fraud analysis.", "auxiliary"),
    "frontend": ("Serves the storefront and calls shopping services.", "critical"),
    "frontend-proxy": ("Routes incoming storefront and observability HTTP requests.", "critical"),
    "grafana": ("Displays operational dashboards from telemetry backends.", "auxiliary"),
    "image-provider": ("Serves product images.", "auxiliary"),
    "jaeger": ("Stores and queries request traces.", "core"),
    "kafka": ("Carries asynchronous order events in the full deployment.", "core"),
    "load-generator": ("Generates synthetic shopping requests.", "auxiliary"),
    "opensearch": ("Stores and searches application logs.", "core"),
    "otel-collector": ("Receives and exports application and container telemetry.", "core"),
    "payment": ("Handles order payment charges.", "critical"),
    "product-catalog": ("Lists products and returns product details.", "core"),
    "prometheus": ("Stores and queries metrics.", "core"),
    "quote": ("Calculates shipment price quotations.", "auxiliary"),
    "recommendation": ("Recommends related products using catalogue data.", "auxiliary"),
    "shipping": ("Quotes and schedules shipments.", "core"),
    "valkey-cart": ("Holds cart state in a Redis-compatible cache.", "critical"),
}
OPERATIONS = {
    "cart": ["GetCart", "AddItem", "EmptyCart"], "checkout": ["PlaceOrder"],
    "payment": ["Charge"], "product-catalog": ["GetProduct", "ListProducts"],
    "recommendation": ["ListRecommendations", "get_product_list"],
    "frontend": ["GET /", "GET /api/cart", "POST /api/checkout", "GET /api/products/{productId}"],
    "valkey-cart": ["Cart read/write", "Connection availability"],
}
SERVICE_RUNBOOKS = {"frontend", "checkout", "payment", "cart", "product-catalog", "recommendation"}


def generate(compose_dir: str | Path, output: str | Path) -> dict:
    """The only subprocess is read-only `docker compose config --format json`."""
    result = subprocess.run(["docker", "compose", "config", "--format", "json"], cwd=compose_dir,
                            capture_output=True, text=True, check=False, timeout=30)
    if result.returncode:
        raise RuntimeError("Compose configuration could not be read; no catalogue was changed")
    raw = json.loads(result.stdout)["services"]
    dependencies = {name: sorted(dep for dep in item.get("depends_on", {}) if not is_sensitive(dep))
                    for name, item in sorted(raw.items()) if not is_sensitive(name)}
    services = {}
    for name, deps in dependencies.items():
        purpose, criticality = PURPOSES.get(name, ("Purpose requires operator review.", "unknown"))
        runbooks = ["container-down", "restart-loop", "dependency-unavailable"]
        if name in SERVICE_RUNBOOKS:
            runbooks.insert(0, name)
        if name in {"cart", "valkey-cart"}:
            runbooks.insert(0, "cache")
        if name in {"otel-collector", "jaeger", "opensearch", "prometheus", "grafana"}:
            runbooks.insert(0, "telemetry-outage")
        if name in {"frontend", "frontend-proxy", "load-generator"}:
            runbooks.append("load")
        services[name] = {"purpose": purpose, "dependencies": deps, "criticality": criticality,
                          "typical_operations": OPERATIONS.get(name, ["Service availability", "Dependency requests"]),
                          "telemetry_hints": ["get_container_health for lifecycle and resource limits",
                                              "error_rate_by_service, p95_latency_by_service and rps_by_service",
                                              "Use fresh traces and logs when the service emits them; missing data is unknown"],
                          "runbooks": runbooks}
    document = {"version": 1, "source": {"command": "docker compose config --format json",
                "directory": str(Path(compose_dir)), "generated_date": "2026-10-23",
                "topology_sha256": hashlib.sha256(json.dumps(dependencies, sort_keys=True).encode()).hexdigest(),
                "scope": "Default Compose configuration; not proof that every configured service is running",
                "dependency_semantics": "Compose startup dependencies, not a complete runtime RPC graph",
                "exclusions": "Diagnostic control-plane services and their edges omitted; no settings retained"},
                "services": services}
    Path(output).write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return document


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compose_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("services.yaml"))
    arguments = parser.parse_args()
    catalogue = generate(arguments.compose_dir, arguments.output)
    print(f"Wrote {len(catalogue['services'])} safe service entries to {arguments.output}")
