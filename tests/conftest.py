"""Keep diagnostic unit-test snapshots separate from recorded acceptance runs."""

import pytest


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
