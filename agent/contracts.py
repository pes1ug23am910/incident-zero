"""Narrow model output schemas: models diagnose; code chooses actions."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .policy import SERVICES, CAUSE_CATEGORIES


class Cause(BaseModel):
    model_config = ConfigDict(extra='forbid')
    component: str
    cause: str = Field(min_length=1, max_length=1200)
    category: Literal['application_flag', 'container_down', 'restart_loop', 'dependency_unavailable',
                      'network', 'resource_starvation', 'load', 'unknown']
    confidence_model: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(max_length=12)
    explains_symptoms: list[str] = Field(max_length=25)
    alternatives_considered: list[str] = Field(default_factory=list, max_length=5)


CAUSE_SCHEMA = Cause.model_json_schema()
CAUSE_SCHEMA['properties']['component']['enum'] = list(SERVICES)
CAUSE_SCHEMA['properties']['explains_symptoms']['items']['enum'] = list(SERVICES)
COMMON = {
    'reason': {'type': 'string', 'description': 'One sentence: why this next read discriminates the hypotheses.'},
    'hypotheses': {'type': 'array', 'items': CAUSE_SCHEMA, 'maxItems': 3,
                   'description': 'Current supported causes only; empty before evidence. Cite returned IDs verbatim.'},
}


def function(name, description, properties, required=()):
    return {'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': {**COMMON, **properties},
                           'required': ['reason', 'hypotheses', *required], 'additionalProperties': False}}}


SERVICE = {'type': 'string', 'enum': list(SERVICES)}
LOOKBACK = {'type': 'integer', 'minimum': 30, 'maximum': 1800, 'description': 'Recent seconds; use 120 for current traces/logs, 600 for trends.'}
FUNCTIONS = [
    function('get_traces', 'Read recent traces and first error spans for one service. Inspect caller traces when a callee is down.',
             {'service': SERVICE, 'lookback_s': LOOKBACK, 'errors_only': {'type': 'boolean'},
              'limit': {'type': 'integer', 'minimum': 1, 'maximum': 10}}, ['service']),
    function('get_logs', 'Read exception/log lines for a service. WARN includes payment errors; TRACE includes unclassified stdout.',
             {'service': SERVICE, 'lookback_s': LOOKBACK,
              'severity_min': {'type': 'string', 'enum': ['TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR']}}, ['service']),
    function('get_metrics', 'Read a named metric or bounded PromQL. Use windows at least 2m. CPU metric is percent of a core.',
             {'promql': {'type': 'string', 'maxLength': 2000}, 'lookback_s': {'type': 'integer', 'minimum': 120, 'maximum': 1800}}, ['promql']),
    function('get_container_health', 'Inspect status, CPU limit, memory limit, OOM and current utilization. Names must be known services.',
             {'names': {'type': 'array', 'items': SERVICE, 'minItems': 1, 'maxItems': 5}}, ['names']),
    function('get_deploy_history', 'Read recent container lifecycle and approved action journal events.', {}),
    function('finish', 'Finish only after all anomalous services are explained and each cause has two independent evidence sources, or no further useful reads remain.',
             {'no_incident': {'type': 'boolean'}, 'limitations': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 8}}, ['no_incident']),
]
