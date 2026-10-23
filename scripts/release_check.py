"""Run release gates 1, 5, 6 and 9; leave unperformed gates unchecked."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .platform_support import ROOT, environment, stamp, table

GATES = {
    1: "Unit and offline tests", 2: "Live preflight", 3: "Three Checkpoint 2 cases",
    4: "Human-approved full loop", 5: "Linux portability / second laptop",
    6: "All report bundles validate", 7: "Independent snapshot audit",
    8: "Claim/evidence review", 9: "Disclosure, process-file and secret scan",
    10: "Team and prior-work sign-off",
}


def offline_env():
    env = dict(os.environ, DOCKER_HOST="tcp://127.0.0.1:1", HTTP_PROXY="http://127.0.0.1:9",
               HTTPS_PROXY="http://127.0.0.1:9", ALL_PROXY="http://127.0.0.1:9", NO_PROXY="")
    for key in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        env[key] = ""
    return env


def repository_scan():
    """Print names/counts only, never matched secret values or source lines."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    names = result.stdout.decode("utf-8").split("\0")
    process = re.compile(r"(^|/)(AGENTS\.md|CLAUDE\.md|PROGRESS\.md|\.codex|\.claude|\.cursor)(/|$)|build[-_]handover|standing[-_]order|prompt[-_]appendix", re.I)
    bad_names = [n for n in names if n and (process.search(n) or n == ".env" or n.startswith(".env."))]
    from agent.llm_router import load_env
    credentials = [v for k, v in load_env().items() if len(v) >= 12 and any(x in k.upper() for x in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))]
    secret_files = []
    for name in names:
        path = ROOT / name
        if not name or not path.is_file():
            continue
        data = path.read_bytes()
        if any(secret.encode() in data for secret in credentials):
            secret_files.append(name)
    history = subprocess.run(["git", "log", "--format=%B"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    trailers = len(re.findall(r"co-authored-by|anthropic|claude|codex|generated with", history, re.I))
    identity = subprocess.run(["git", "log", "--format=%an <%ae>|%cn <%ce>"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    expected = "Yash Verma <pes1ug23am910@pesu.pes.edu>"
    wrong = [line for line in identity.splitlines() if line != expected + "|" + expected]
    print(f"Tracked forbidden process/credential paths: {len(bad_names)}")
    for name in bad_names:
        print("  path: " + name)
    print(f"Tracked files matching configured secret values: {len(secret_files)}")
    for name in secret_files:
        print("  path: " + name)
    print(f"Forbidden commit-message matches: {trailers}; unexpected authorship records: {len(wrong)}")
    return int(bool(bad_names or secret_files or trailers or wrong))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", type=int, choices=(1, 5, 6, 9), action="append",
                        help="run selected gates only; default runs all four")
    parser.add_argument("--scan-only", action="store_true", help="tracked repository scan, no tests")
    args = parser.parse_args(argv)
    environment()
    if args.scan_only:
        return repository_scan()
    output = ROOT / ".build/release"
    output.mkdir(parents=True, exist_ok=True)
    identity = stamp()
    results = {}
    for gate in args.gate or (1, 5, 6, 9):
        commands = {
            1: [[sys.executable, "-m", "pytest", "-q", "-m", "not live", "--basetemp=.build/pytest-release"]],
            5: [[sys.executable, "-m", "scripts.crossplatform_check"]],
            6: [[sys.executable, "-m", "scripts.validate_reports"]],
            9: [[sys.executable, "-m", "pytest", "-q", "tests/test_no_flag_reads.py", "tests/test_agent_isolation.py", "--basetemp=.build/pytest-disclosure"],
                [sys.executable, "-m", "scripts.release_check", "--scan-only"]],
        }[gate]
        code = 0
        with (output / f"{identity}-gate{gate}.log").open("w", encoding="utf-8") as log:
            for command in commands:
                # Tests and retained-evidence validation cannot use live endpoints.
                env = offline_env() if gate in (1, 6) or command[2] == "pytest" else None
                process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
                for line in process.stdout:
                    print(line, end="", flush=True)
                    log.write(line)
                code |= process.wait()
        results[gate] = "PASS" if code == 0 else "FAIL"
    rows = [(f"[{'x' if results.get(i) == 'PASS' else ' '}] {i}. {name}", results.get(i, "NOT VERIFIED"),
             f"{identity}-gate{i}.log" if i in results else "manual evidence required") for i, name in GATES.items()]
    content = table(rows)
    (output / (identity + ".md")).write_text(content, encoding="utf-8")
    (output / (identity + ".json")).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("\n" + content)
    print("Only performed gates are ticked. This is not a declaration that the full release is ready.")
    return int(any(value == "FAIL" for value in results.values()))


if __name__ == "__main__":
    raise SystemExit(main())
