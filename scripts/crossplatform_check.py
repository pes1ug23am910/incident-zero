"""Run the offline suite in a disposable Linux Python 3.11 container."""
import argparse
import os
from pathlib import Path
import subprocess

from .platform_support import ROOT, environment, stamp


def docker_command(root=ROOT):
    # No Docker socket, model keys, .env, host state or live network reaches pytest.
    # Include uncommitted source edits; exclude machine-local build/runtime state.
    command = r'''set -eu
mkdir /work
tar -C /repo --exclude=.git --exclude=.venv --exclude=.env --exclude='.env.*' --exclude=.build --exclude=runs --exclude=STOP --exclude='faultctl/.state' --exclude='faultctl/.pristine' --exclude='action_api/log.jsonl' --exclude='memory/store' --exclude='knowledge/index.sqlite' --exclude=__pycache__ --exclude=.pytest_cache -cf - . | tar -C /work -xf -
cd /work
python -m pip install -e '.[test]' -q
export DOCKER_HOST=tcp://127.0.0.1:1 HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 ALL_PROXY=http://127.0.0.1:9 NO_PROXY=
python -m pytest -q -m 'not live' --basetemp=/tmp/incident-zero-pytest
'''
    return ["docker", "run", "--rm", "--mount", f"type=bind,source={Path(root).resolve()},target=/repo,readonly",
            "-w", "/tmp", "python:3.11", "bash", "-c", command]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".build/portability")
    parser.add_argument("--print-command", action="store_true", help="preview without starting a container")
    args = parser.parse_args(argv)
    environment()
    command = docker_command()
    if args.print_command:
        print(command)
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / (stamp() + ".log")
    env = dict(os.environ, MSYS_NO_PATHCONV="1", MSYS2_ARG_CONV_EXCL="*")
    with path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", env=env)
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
        code = process.wait()
        summary = f"{'PASS' if code == 0 else 'FAIL'} Linux python:3.11 offline suite; exit {code}\n"
        log.write(summary)
    print(summary + "Record: " + str(path))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
