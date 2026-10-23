"""Named PromQL with the names verified on the demo's OTLP receiver."""

from .common import get_json, prometheus
from .redact import APPLICATION_SPAN_SELECTOR

CANDIDATES = {
    "calls": ("traces_span_metrics_calls_total", "calls_total"),
    "duration": ("traces_span_metrics_duration_milliseconds_bucket", "duration_milliseconds_bucket"),
    "cpu": ("container_cpu_utilization_ratio", "container_cpu_utilization"),
    "memory": ("container_memory_usage_total_bytes", "container_memory_usage_total", "container_memory_usage_bytes", "container_memory_usage"),
    "http": ("httpcheck_status", "httpcheck_status_code"),
}


def build_queries(names=()):
    selected = {key: next((n for n in options if n in names), options[0])
                for key, options in CANDIDATES.items()}
    calls = selected["calls"]
    # The connector exports about once a minute: rate needs at least two
    # samples. All span kinds also cover services that only emit client spans.
    selector = APPLICATION_SPAN_SELECTOR
    denominator = f"sum by (service_name) (rate({calls}{{{selector}}}[2m]))"
    # Missing error-labelled series means zero errors only if calls exist.
    errors = f'sum by (service_name) (rate({calls}{{{selector},status_code="STATUS_CODE_ERROR"}}[2m]))'
    return {
        "error_rate_by_service": f"({errors} or (0 * {denominator})) / {denominator}",
        "p95_latency_by_service": f'histogram_quantile(0.95, sum by (le, service_name) (rate({selected["duration"]}{{{selector}}}[2m])))',
        "rps_by_service": denominator,
        "container_cpu": selected["cpu"],
        "container_memory": selected["memory"],
        "frontend_http_check": selected["http"],
    }


QUERIES = build_queries()


def named_query(name):
    if name not in QUERIES:
        raise ValueError(f"Unknown named query: {name}")
    response = get_json(prometheus() + "/api/v1/label/__name__/values")
    return build_queries(response.get("data", []))[name]
