"""Report-only knowledge presentation; no telemetry or action backend calls."""
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest

from ui.mock_api import create_app


APP_JS = Path(__file__).resolve().parents[1] / "ui/static/app.js"


def knowledge_report():
    runbook = {
        "id": "kb:container-down#remediation", "score": 4.321,
        "text": "Confirm the container is stopped before requesting restart_service.",
        "file": "knowledge/runbooks/container-down.md", "section": "remediation",
        "version": "1", "sha256": "a" * 64,
    }
    memory = {
        "id": "mem:earlier-incident", "score": 0.8,
        "text": "Restart did not recover the service; the incident was escalated.",
        "file": "memory/store/earlier-incident.json", "section": "outcome",
        "version": "1", "sha256": "b" * 64,
    }
    return {
        "incident_id": "knowledge-ui", "status": "needs_human",
        "runbook_refs": [runbook], "memory_refs": [memory],
        "knowledge_consulted": {
            "enabled": True, "mode": "bm25", "queries": ["cart container stopped"],
            "runbook_refs": [runbook], "memory_refs": [memory], "service_refs": [],
            "limitations": ["The prior incident does not establish the current cause."],
        },
    }


def render(report, incidents=()):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed for the dependency-free browser renderer checks")
    driver = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(process.argv[1], 'utf8').split('\nasync function api(')[0];
const script = source + '\nstate.incidents = input.incidents; JSON.stringify({panel: knowledgePanel(input.report), citations: proposalCitations(input.report)});';
process.stdout.write(vm.runInNewContext(script, {input}));
"""
    result = subprocess.run(
        [node, "-e", driver, str(APP_JS)],
        input=json.dumps({"report": report, "incidents": list(incidents)}),
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(result.stdout)


def test_mock_report_preserves_consulted_context_and_citations(tmp_path):
    report = knowledge_report()
    bundle = tmp_path / "reports" / report["incident_id"]
    bundle.mkdir(parents=True)
    path = bundle / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    before = path.read_bytes()
    with TestClient(create_app(tmp_path / "reports", tmp_path / "runs")) as client:
        response = client.get("/api/incidents/knowledge-ui")
        assert response.status_code == 200
        for field in ("knowledge_consulted", "runbook_refs", "memory_refs"):
            assert response.json()[field] == report[field]
    assert path.read_bytes() == before


def test_citations_resolve_to_recorded_snippets_with_outcomes():
    report = knowledge_report()
    rendered = render(report, [{"id": "earlier-incident"}])
    assert "What the agent consulted" in rendered["panel"]
    assert "Restart did not recover" in rendered["panel"]
    assert 'data-open="earlier-incident"' in rendered["panel"]
    assert "Similarity 4.321" in rendered["panel"]
    assert "not diagnosis confidence" in rendered["panel"]
    assert report["knowledge_consulted"]["limitations"][0] in rendered["panel"]
    links = re.findall(r'href="#([^"]+)"', rendered["citations"])
    assert len(links) == 2
    assert all(f'id="{anchor}"' in rendered["panel"] for anchor in links)
    assert "evidence and policy determine" in rendered["citations"]
    assert 'data-open="earlier-incident"' not in render(report)["panel"]


def test_untrusted_snippets_and_paths_cannot_create_markup_or_external_links():
    report = knowledge_report()
    payload = '<img src=x onerror="alert(1)">'
    ref = report["knowledge_consulted"]["runbook_refs"][0]
    ref.update(id='kb:"><script>alert(1)</script>', file="javascript:alert(1)",
               text=payload, section=payload, version=payload, sha256=payload)
    report["knowledge_consulted"]["queries"] = [payload]
    report["knowledge_consulted"]["limitations"] = [payload]
    rendered = render(report)
    for html in rendered.values():
        assert "<script>" not in html and "<img" not in html
        assert 'href="javascript:' not in html
        assert all(href.startswith("#knowledge-ref-") for href in re.findall(r'href="([^"]+)"', html))
    assert "&lt;img" in rendered["panel"]


@pytest.mark.parametrize("report,message", [
    ({}, "does not record knowledge retrieval"),
    ({"knowledge_consulted": {"enabled": False}}, "retrieval was disabled"),
    ({"knowledge_consulted": {"enabled": True, "mode": "bm25"}}, "No matching context"),
])
def test_reports_distinguish_absent_disabled_and_empty_context(report, message):
    rendered = render(report)
    assert message in rendered["panel"]
    assert not rendered["citations"]


def test_disabled_retrieval_never_displays_stale_references():
    report = deepcopy(knowledge_report())
    report["knowledge_consulted"]["enabled"] = False
    rendered = render(report)
    assert "kb:" not in rendered["panel"] and "mem:" not in rendered["panel"]
    assert not rendered["citations"]
