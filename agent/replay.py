"""Replay recorded decisions and tools through the real graph without network.

This module reads observations, never evaluation answers. The original snapshots
are copied byte-for-byte into a fresh run and validated by the shared evidence
loader; the source fixture and original run remain immutable.
"""
from __future__ import annotations

from copy import deepcopy
from functools import partial
import hashlib
import json
from pathlib import Path
from typing import Any

from tools import evidence as snapshots
from .llm_router import ModelUnavailable, now


class ReplayMismatch(RuntimeError):
    """Current graph requests differ from the recorded trajectory."""


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ReplayRouter:
    def __init__(self, fixture_dir: str | Path, run_dir: str | Path):
        self.fixture_dir = Path(fixture_dir)
        self.run_dir = snapshots.run_path(run_dir, create=True)
        journal = _jsonl(self.fixture_dir / "llm.jsonl")
        self.records = [entry for entry in journal if entry.get("ok")]
        self.terminal_failure = bool(journal and not journal[-1].get("ok"))
        self.failure_consumed = False
        self.entries: list[dict] = []
        self.index = 0
        self.secrets = ()

    def complete(self, messages, functions, *, purpose="investigate"):
        if self.index >= len(self.records):
            if self.terminal_failure and not self.failure_consumed:
                self.failure_consumed = True
                entry = {"timestamp": now(), "purpose": purpose, "provider": "offline_replay",
                         "model": "offline-replay:unavailable", "ok": False, "error": "ModelUnavailable",
                         "request": {"messages": messages, "tools": functions},
                         "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0}
                self.entries.append(entry)
                with (self.run_dir / "llm.jsonl").open("a", encoding="utf-8") as output:
                    output.write(json.dumps(entry, ensure_ascii=False) + "\n")
                raise ModelUnavailable("All configured structured model routes failed; inspect sanitized llm.jsonl")
            raise ReplayMismatch("Graph requested a model decision beyond the recorded trajectory")
        record = self.records[self.index]
        calls = record.get("response", {}).get("tool_calls", [])
        if not calls:
            raise ReplayMismatch("Successful recorded decision has no structured tool call")
        call = calls[0]["function"]
        allowed = {function["function"]["name"] for function in functions}
        if call["name"] not in allowed:
            raise ReplayMismatch("Recorded tool is not allowed at this point in the graph")
        arguments = json.loads(call["arguments"]) if isinstance(call["arguments"], str) else deepcopy(call["arguments"])
        self.index += 1
        entry = {
            "timestamp": now(), "purpose": purpose, "provider": "offline_replay",
            "model": "offline-replay:" + record.get("model", "not_available"),
            "ok": True, "request": {"messages": messages, "tools": functions},
            "response": deepcopy(record["response"]),
            "recorded_model": record.get("model"), "recorded_usage": record.get("usage", {}),
            "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0,
        }
        self.entries.append(entry)
        with (self.run_dir / "llm.jsonl").open("a", encoding="utf-8") as output:
            output.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"name": call["name"], "arguments": arguments, "model": entry["model"]}

    def summary(self):
        models = list(dict.fromkeys(entry["model"] for entry in self.entries if entry.get("ok")))
        return {"model": ", ".join(models) or "offline-replay:unavailable", "models_used": models,
                "llm_calls": len(self.entries), "tokens_input": 0, "tokens_output": 0,
                "estimated_cost_usd": 0}

    def assert_complete(self):
        if self.index != len(self.records):
            raise ReplayMismatch(f"Graph consumed {self.index} of {len(self.records)} recorded decisions")
        if self.terminal_failure and not self.failure_consumed:
            raise ReplayMismatch("Graph did not reproduce the recorded terminal provider failure")


class ReplayTools:
    NAMES = ("health_table", "get_metrics", "get_traces", "get_logs", "get_container_health", "get_deploy_history")

    def __init__(self, fixture_dir: str | Path):
        self.fixture_dir = Path(fixture_dir).resolve()
        self.records = _jsonl(self.fixture_dir / "tools.jsonl")
        self.index = 0
        self.run_dir = None

    def toolset(self) -> dict[str, Any]:
        return {name: partial(self.read, name) for name in self.NAMES}

    def read(self, name: str, *, run_dir, **arguments):
        if self.index >= len(self.records):
            raise ReplayMismatch("Graph requested a tool beyond the recorded trajectory")
        recorded = self.records[self.index]
        if name != recorded["tool"] or arguments != recorded["arguments"]:
            raise ReplayMismatch(f"Tool order or arguments changed at recorded step {self.index + 1}: expected {recorded['tool']}")
        target_run = snapshots.run_path(run_dir, create=True)
        if self.run_dir is not None and self.run_dir != target_run:
            raise ReplayMismatch("One replay cannot write evidence into multiple runs")
        self.run_dir = target_run
        result = deepcopy(recorded["result"])
        paths = {}
        for identifier in result.get("evidence_ids", []):
            target = snapshots.snapshot_path(target_run, identifier)
            source = self.fixture_dir / "evidence" / target.name
            if source.resolve() != source or not source.is_file():
                raise ReplayMismatch("Fixture evidence is missing or resolves through a symbolic link")
            raw = source.read_bytes()
            try:
                with target.open("xb") as output:
                    output.write(raw)
            except FileExistsError:
                if target.read_bytes() != raw:
                    raise ReplayMismatch("Replay would replace an existing immutable evidence record")
            try:
                snapshots.load_snapshot(target, identifier)
            except (ValueError, OSError) as error:
                raise ReplayMismatch(f"Recorded evidence failed validation: {error}") from error
            paths[identifier] = target.relative_to(snapshots.ROOT.resolve()).as_posix()
        result["run_dir"] = target_run.relative_to(snapshots.ROOT.resolve()).as_posix()
        result["evidence_paths"] = paths
        self.index += 1
        return result

    def resolve(self, identifier: str) -> dict:
        if self.run_dir is None:
            raise ReplayMismatch("No replay evidence has been observed")
        return snapshots.load_snapshot(snapshots.snapshot_path(self.run_dir, identifier), identifier)

    def assert_complete(self):
        if self.index != len(self.records):
            raise ReplayMismatch(f"Graph consumed {self.index} of {len(self.records)} recorded tools")


def replay(fixture_dir: str | Path, *, run_id: str | None = None, output: str | Path | None = None) -> dict:
    """Run the complete production graph with recorded I/O and offline validation."""
    from .run import run

    fixture_dir = Path(fixture_dir)
    run_dir = snapshots.run_path(run_id, create=True)
    router = ReplayRouter(fixture_dir, run_dir)
    reads = ReplayTools(fixture_dir)
    alert = json.loads((fixture_dir / "alert.json").read_text(encoding="utf-8"))
    # A fresh metadata slug keeps fixture names out of the model context.
    incident = "replay-" + hashlib.sha256(run_dir.name.encode()).hexdigest()[:16]
    result = run(alert, incident, output=output, run_id=run_dir,
                 router=router, toolset=reads.toolset(), resolver=reads.resolve)
    router.assert_complete()
    reads.assert_complete()
    return result
