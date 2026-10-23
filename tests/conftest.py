"""Keep diagnostic unit-test snapshots separate from recorded acceptance runs."""

import pytest


@pytest.fixture
def offline_action_service(tmp_path):
    """Real approval policy with synthetic world/telemetry and no allowed writes."""
    from action_api.service import ActionService
    from action_api.verify import FIELDS, Verifier, signals

    class Executor:
        def __init__(self):
            self.mutations = []

        def snapshot(self, plan):
            return {'synthetic_world': True, 'target': plan['target']}

        def execute(self, plan, before):
            self.mutations.append(plan)
            raise AssertionError('A diagnosis/checkpoint test attempted execution')

        def rollback(self, plan, before):
            raise AssertionError('A diagnosis/checkpoint test attempted rollback')

    def sample(alert, run_id):
        return {'available': True,
                'values': ['running' if FIELDS.get(item['signal']) == 'status' else 0
                           for item in signals(alert)],
                'requests_observed': 40, 'load_running': True, 'evidence_ids': []}

    return ActionService(tmp_path, executor=Executor(), verifier=Verifier(sampler=sample))


@pytest.fixture
def local_jaeger_endpoint(monkeypatch):
    from tools import common
    monkeypatch.setattr(common, 'jaeger_endpoints', lambda: ['http://localhost:8080/jaeger/ui/api'])


@pytest.fixture(autouse=True)
def isolated_evidence_runs(tmp_path, monkeypatch):
    from tools import evidence

    monkeypatch.setattr(evidence, "ROOT", tmp_path)
    token = evidence.CURRENT_RUN.set(None)
    yield
    evidence.CURRENT_RUN.reset(token)
