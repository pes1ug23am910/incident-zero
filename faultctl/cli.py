"""Sanctioned operator interface. All mutation stays behind this CLI."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import requests


ROOT = Path(__file__).resolve().parents[1]
FLAGS = {
    "payment-failure": ("paymentFailure", "100%", "payment"),
    "payment-unreachable": ("paymentUnreachable", "on", "payment"),
    "cart-intermittent": ("cartFailure", "on", "cart"),
    "catalog-one-product": ("productCatalogFailure", "on", "product-catalog"),
    "recommendation-leak": ("recommendationCacheFailure", "on", "recommendation"),
    "ad-high-cpu": ("adHighCpu", "on", "ad"),
    "ad-gc": ("adManualGc", "on", "ad"),
    "homepage-flood": ("loadGeneratorFloodHomepage", "on", "load-generator"),
}
INFRA = ("container-stopped", "restart-loop", "cache-unavailable", "network-latency", "cpu-starve", "memory-starve")


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    write_bytes(path, (json.dumps(value, indent=2) + "\n").encode("utf-8"))


def write_bytes(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


class FaultError(RuntimeError):
    pass


class Controller:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.package = self.root / "faultctl"
        self.config = json.loads((self.package / "config.yaml").read_text(encoding="utf-8"))
        self.demo = Path(os.environ.get("INCIDENT_ZERO_DEMO_DIR", self.config["demo_dir"]))
        if not self.demo.is_absolute():
            self.demo = (self.root / self.demo).resolve()
        self.state_dir = self.package / ".state"
        self.state_path = self.state_dir / "state.json"
        self.pristine = self.package / ".pristine" / "demo.flagd.json"
        self.source = self.demo / "src" / "flagd" / "demo.flagd.json"
        self.active = self.state_dir / "flags" / "demo.flagd.json"
        self.override = self.state_dir / "injection.compose.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def run(self, args, timeout=90, check=True):
        env = dict(os.environ, DEMO_VERSION=self.config["demo_version"])
        result = subprocess.run(args, cwd=self.root, env=env, text=True, capture_output=True, timeout=timeout)
        if check and result.returncode:
            raise FaultError(f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}{result.stderr}")
        return result

    def compose(self, *args, override=None, timeout=180):
        command = ["docker", "compose", "--project-directory", str(self.demo), "-f", str(self.demo / self.config["compose_file"])]
        use_override = self.override.exists() if override is None else override
        if use_override:
            command += ["-f", str(self.override)]
        return self.run(command + list(args), timeout=timeout)

    def services(self):
        return json.loads(self.compose("config", "--format", "json", override=False).stdout)["services"]

    def target(self, name):
        services = self.services()
        if name not in services or name not in self.config["containers"]:
            raise FaultError(f"Service is not allowlisted in the official minimal stack: {name}")
        container = services[name].get("container_name", name)
        if container != self.config["containers"][name]:
            raise FaultError(f"Container mapping differs from allowlist: {name}")
        return container

    def state(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"incidents": [], "flag_override": False}

    @contextmanager
    def lock(self):
        path = self.state_dir / "mutation.lock"
        with path.open("a+b") as handle:
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + 120
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise FaultError("Another mutation is in progress; lock timed out")
                    time.sleep(0.1)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def ensure_pristine(self):
        source_bytes = self.source.read_bytes()  # Operator-only baseline/read-back.
        if not self.pristine.exists():
            self.pristine.parent.mkdir(parents=True, exist_ok=True)
            with self.pristine.open("xb") as handle:
                handle.write(source_bytes)
        if self.pristine.read_bytes() != source_bytes:
            raise FaultError("Official source differs from saved pristine bytes; refusing to overwrite either")
        json.loads(source_bytes)
        return hashlib.sha256(source_bytes).hexdigest()

    def inspect(self, target):
        return json.loads(self.run(["docker", "inspect", target]).stdout)[0]

    def prepare_overlay(self):
        """Prepare the persistent directory before Compose establishes its mount."""
        self.ensure_pristine()
        write_bytes(self.active, self.pristine.read_bytes())
        write_json(self.override, {"services": {"flagd": {"volumes": [{
            "type": "bind", "source": str(self.active.parent),
            "target": "/etc/flagd", "read_only": True,
        }]}}})

    def require_injection_mount(self):
        if not self.override.exists() or not self.active.exists():
            raise FaultError("Injection directory is not prepared; run faultctl up before injection")
        if not self.has_injection_mount(self.inspect("flagd")):
            raise FaultError("Injection directory is not mounted; run faultctl up before injection")

    def up(self):
        with self.lock():
            if self.state()["incidents"]:
                raise FaultError("Active incident state exists; run reset before up")
            self.prepare_overlay()
            output = self.compose("up", "-d")
            self.require_injection_mount()
            return {"ok": True, "output": output.stdout + output.stderr}

    def netem(self, target, *args, check=True):
        return self.run(["docker", "run", "--rm", "--network", f"container:{target}", "--cap-add", "NET_ADMIN", self.config["netem_image"], *args], timeout=45, check=check)

    def inject(self, incident, args):
        with self.lock():
            if (self.root / "STOP").exists():
                raise FaultError("STOP exists; injection refused (reset is still allowed)")
            if incident not in FLAGS and incident not in INFRA:
                raise FaultError(f"Unknown incident: {incident}")
            self.ensure_pristine()
            target_name = FLAGS[incident][2] if incident in FLAGS else ("valkey-cart" if incident == "cache-unavailable" else args.svc)
            if not target_name:
                raise FaultError(f"{incident} requires --svc")
            target = self.target(target_name)
            if incident == "network-latency" and (not re.fullmatch(r"[1-9]\d*(?:ms|s)", args.delay) or not 0 <= args.loss <= 100):
                raise FaultError("Delay must be a positive ms/s duration and loss must be 0..100")
            if incident in FLAGS:
                key, default, _ = FLAGS[incident]
                variant = args.rate if incident == "payment-failure" else default
                baseline = json.loads(self.pristine.read_text(encoding="utf-8"))
                if variant not in baseline["flags"][key]["variants"]:
                    raise FaultError(f"Unsupported variant for {incident}: {variant}")
                self.require_injection_mount()
            snapshot = self.inspect(target)
            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:6]
            run_dir = self.root / "runs" / run_id
            record = {
                "incident_id": incident, "mechanism": "feature_flag" if incident in FLAGS else incident,
                "target": target_name, "params": {"rate": args.rate} if incident in FLAGS else {"delay": args.delay, "loss": args.loss},
                "injected_at": now(), "expected_signals": self.signals(incident), "run_id": run_id,
                "phase": "prepared", "before": {"NanoCpus": snapshot["HostConfig"].get("NanoCpus", 0), "Memory": snapshot["HostConfig"].get("Memory", 0), "MemorySwap": snapshot["HostConfig"].get("MemorySwap", 0), "StartedAt": snapshot["State"].get("StartedAt"), "RestartCount": snapshot.get("RestartCount", 0)},
            }
            state = self.state()
            state["incidents"].append(record)
            if incident in FLAGS:
                state["flag_override"] = True
            write_json(self.state_path, state)  # Persist intent before any external mutation.
            write_json(run_dir / "injected.json", record)
            try:
                if incident in FLAGS:
                    self.set_flag(key, variant)
                    log_result = self.run(["docker", "logs", "flagd", "--since", "20s"])
                    result = {"file_variant": variant, "logs": (log_result.stdout + log_result.stderr)[-1800:]}
                elif incident in ("container-stopped", "cache-unavailable"):
                    self.run(["docker", "stop", target])
                    result = {"status": self.inspect(target)["State"]["Status"]}
                    if result["status"] != "exited":
                        raise FaultError("Stopped container did not read back exited")
                elif incident == "cpu-starve":
                    self.run(["docker", "update", "--cpus", "0.05", target])
                    result = {"NanoCpus": self.inspect(target)["HostConfig"]["NanoCpus"]}
                    if result["NanoCpus"] != 50_000_000:
                        raise FaultError("CPU limit failed read-back")
                elif incident == "memory-starve":
                    self.run(["docker", "update", "--memory", "48m", "--memory-swap", "48m", target])
                    result = {"Memory": self.inspect(target)["HostConfig"]["Memory"], "MemorySwap": self.inspect(target)["HostConfig"]["MemorySwap"]}
                    if result["Memory"] != 48 * 1024**2 or result["MemorySwap"] != 48 * 1024**2:
                        raise FaultError("Memory limit failed read-back")
                elif incident == "network-latency":
                    self.netem(target, "qdisc", "replace", "dev", "eth0", "root", "netem", "delay", args.delay, "loss", f"{args.loss}%")
                    result = {"qdisc": self.netem(target, "qdisc", "show", "dev", "eth0").stdout.strip()}
                    if "netem" not in result["qdisc"]:
                        raise FaultError("Netem did not read back")
                else:
                    self.run(["docker", "restart", target])
                    result = {"StartedAt": self.inspect(target)["State"]["StartedAt"], "RestartCount": self.inspect(target)["RestartCount"], "manual_restarts": 1}
                    marker = run_dir / "loop.json"
                    write_json(marker, {"cancelled": False, "target": target_name, "manual_restarts": 1})
                    log = (run_dir / "loop.log").open("ab")
                    try:
                        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                        worker = subprocess.Popen([sys.executable, "-m", "faultctl", "_loop", str(marker)], cwd=self.root, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=creationflags, start_new_session=os.name != "nt")
                    finally:
                        log.close()
                    (run_dir / "loop.pid").write_text(str(worker.pid), encoding="ascii")
                    result["worker_pid"] = worker.pid
                    result["note"] = "Manual docker restart does not increment RestartCount; StartedAt and manual_restarts are the observable loop evidence."
                record.update(phase="applied", readback=result)
            except Exception as error:
                record.update(phase="failed", error=str(error))
                raise
            finally:
                write_json(run_dir / "injected.json", record)
                write_json(self.state_path, state)
            return record

    @staticmethod
    def signals(incident):
        if incident in ("cpu-starve", "memory-starve"):
            return ["Container resource limit reduced", "Latency, saturation or out-of-memory symptoms"]
        if incident in ("container-stopped", "cache-unavailable", "restart-loop"):
            return ["Container state or start time changes", "Dependency errors in traces and logs"]
        if incident == "network-latency":
            return ["Increased trace duration", "RPC timeout or network errors"]
        return ["Changed application error, latency, resource or traffic metrics", "Correlated traces and logs"]

    def set_flag(self, key, variant):
        self.require_injection_mount()
        current = json.loads(self.active.read_text(encoding="utf-8"))
        current["flags"][key]["defaultVariant"] = variant
        write_json(self.active, current)
        time.sleep(2)
        if json.loads(self.active.read_text(encoding="utf-8"))["flags"][key]["defaultVariant"] != variant:
            raise FaultError("Active injection file failed read-back")
        if not self.has_injection_mount(self.inspect("flagd")):
            raise FaultError("Active injection directory is not mounted in the flag service")
        logs = self.run(["docker", "logs", "flagd", "--since", "20s"])
        if not re.search(r"sync|reload|configuration|flag.*(?:update|evaluat)|provider", logs.stdout + logs.stderr, re.IGNORECASE):
            raise FaultError("No synchronization/reload log from flag service")
        self.ensure_pristine()

    def has_injection_mount(self, inspected):
        suffix = f"/{self.root.name}/faultctl/.state/flags".lower()
        return any(mount.get("Destination") == "/etc/flagd" and mount.get("Source", "").replace("\\", "/").lower().rstrip("/").endswith(suffix) for mount in inspected.get("Mounts", []))

    def cancel_loops(self, state):
        for record in state["incidents"]:
            marker = self.root / "runs" / record["run_id"] / "loop.json"
            if marker.exists():
                value = json.loads(marker.read_text(encoding="utf-8"))
                value["cancelled"] = True
                write_json(marker, value)

    def reset(self, timeout_s=90):
        errors = []
        checks = []
        with self.lock():
            state = self.state()
            self.cancel_loops(state)
            try:
                baseline_sha = self.ensure_pristine()
                if self.active.exists() or self.override.exists():
                    write_bytes(self.active, self.pristine.read_bytes())
                checks.append({"check": "pristine-source", "ok": True, "sha256": baseline_sha})
            except Exception as error:
                errors.append(str(error))
            touched = set()
            expected_limits = {}
            netem_targets = set()
            for record in state["incidents"]:
                target = record["target"]
                if record["incident_id"] == "network-latency":
                    netem_targets.add(target)
                    try:
                        if self.inspect(target)["State"]["Status"] == "running":
                            self.netem(target, "qdisc", "del", "dev", "eth0", "root", check=False)
                            qdisc = self.netem(target, "qdisc", "show", "dev", "eth0").stdout
                            if "netem" in qdisc:
                                raise FaultError(f"Netem remains on {target}: {qdisc}")
                            checks.append({"check": f"netem:{target}", "ok": True, "qdisc": qdisc.strip()})
                        else:
                            touched.add(target)  # Recreating also replaces its network namespace.
                    except Exception as error:
                        errors.append(str(error))
                if record["incident_id"] not in FLAGS and record["incident_id"] != "network-latency":
                    touched.add(target)
                    expected_limits.setdefault(target, record["before"])
            try:
                if state["flag_override"] or self.override.exists():
                    self.require_injection_mount()
                if "flagd" in touched:
                    raise FaultError("Reset cannot recreate the control service; restore its infrastructure before retrying")
                for target in touched:
                    self.target(target)
                if touched:
                    self.compose("up", "-d", "--no-deps", "--force-recreate", *sorted(touched))
                self.compose("up", "-d", "--no-recreate")
                for target, expected in expected_limits.items():
                    actual = self.inspect(target)["HostConfig"]
                    for field in ("NanoCpus", "Memory", "MemorySwap"):
                        if actual.get(field, 0) != expected[field]:
                            raise FaultError(f"{target}.{field} is {actual.get(field)}, expected {expected[field]}")
                    checks.append({"check": f"limits:{target}", "ok": True})
                if self.override.exists():
                    self.require_injection_mount()
                    checks.append({"check": "persistent-injection-mount", "ok": True})
                for target in sorted(netem_targets):
                    qdisc = self.netem(target, "qdisc", "show", "dev", "eth0").stdout
                    if "netem" in qdisc:
                        raise FaultError(f"Netem remains after restoration on {target}: {qdisc}")
                    checks.append({"check": f"netem-final:{target}", "ok": True, "qdisc": qdisc.strip()})
                if self.active.exists() and self.active.read_bytes() != self.pristine.read_bytes():
                    raise FaultError("Active injection file differs from pristine after reset")
                self.ensure_pristine()
            except Exception as error:
                errors.append(str(error))
            fault_state_clean = not errors
            if fault_state_clean:
                write_json(self.state_path, {"incidents": [], "flag_override": False, "last_reset": now()})
            deadline = time.monotonic() + timeout_s
            readiness = {"ok": False, "checks": []}
            while True:
                readiness = self.status(traffic_seconds=0)
                if readiness["ok"]:
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(2)
            checks.extend(readiness["checks"])
            if not readiness["ok"]:
                errors.append("Stack readiness did not pass before reset deadline")
            if not fault_state_clean:
                state["reset_errors"] = errors
                write_json(self.state_path, state)
            return {"ok": not errors, "fault_state_clean": fault_state_clean, "stack_ready": readiness["ok"], "checks": checks, "errors": errors, "reset_at": now()}

    def status(self, traffic_seconds=0):
        from tools.common import jaeger_json, read_with_retry, READ_TIMEOUT_S

        checks = []
        started = time.monotonic()
        def check(name, operation):
            tick = time.monotonic()
            try:
                detail = operation()
                checks.append({"check": name, "ok": True, "elapsed_s": round(time.monotonic() - tick, 3), "detail": detail})
            except Exception as error:
                checks.append({"check": name, "ok": False, "elapsed_s": round(time.monotonic() - tick, 3), "detail": str(error)})
        def containers():
            services = self.services()
            names = [value.get("container_name", name) for name, value in services.items()]
            values = json.loads(self.run(["docker", "inspect", *names]).stdout)
            bad = {item["Name"].lstrip("/"): item["State"]["Status"] for item in values if item["State"]["Status"] != "running" or item["State"].get("Health", {}).get("Status") == "unhealthy"}
            if bad:
                raise FaultError(json.dumps(bad))
            return {"running": len(values), "expected": len(names)}
        def http(url):
            def read():
                response = requests.get(url, timeout=READ_TIMEOUT_S)
                response.raise_for_status()
                return response
            return read_with_retry(read)
        def jaeger():
            names = jaeger_json("/services")["data"]
            missing = sorted({"frontend", "checkout", "payment"} - set(names))
            if missing:
                raise FaultError("Missing trace services: " + ", ".join(missing))
            return names
        def opensearch():
            result = self.run(["docker", "port", "opensearch", "9200"], check=False)
            if result.returncode == 0 and result.stdout.strip():
                port = result.stdout.splitlines()[0].rsplit(":", 1)[1]
                return http(f"http://localhost:{port}/_cluster/health").json()["status"]
            return json.loads(self.run(["docker", "exec", "opensearch", "curl", "-fsS", "http://localhost:9200/_cluster/health"]).stdout)["status"]
        def traffic():
            def recent():
                end = int(time.time() * 1_000_000)
                response = jaeger_json("/traces", params={"service": "frontend", "start": end - 120_000_000,
                                                        "end": end, "limit": 100})
                return {trace["traceID"] for trace in response["data"]}
            before = recent()
            time.sleep(traffic_seconds)
            after = recent()
            added = len(after - before)
            if not added:
                raise FaultError("No new frontend traces in traffic observation window")
            return {"before_count": len(before), "after_count": len(after), "new_trace_ids": added, "window_s": traffic_seconds}
        check("containers", containers)
        check("shop", lambda: http("http://localhost:8080").status_code)
        check("prometheus", lambda: http("http://localhost:9090/-/ready").status_code)
        check("jaeger-services", jaeger)
        check("opensearch", opensearch)
        check("load-generator-ui", lambda: http("http://localhost:8080/loadgen/").status_code)
        if traffic_seconds:
            check("frontend-traffic", traffic)
        return {"ok": all(item["ok"] for item in checks), "checks": checks, "elapsed_s": round(time.monotonic() - started, 3)}

    def loop(self, marker):
        marker = Path(marker).resolve()
        if not marker.is_relative_to(self.root / "runs"):
            raise FaultError("Loop marker must be under this repository's runs directory")
        while marker.exists():
            for _ in range(80):
                if not marker.exists() or json.loads(marker.read_text(encoding="utf-8")).get("cancelled") or (self.root / "STOP").exists():
                    return
                time.sleep(0.25)
            with self.lock():
                value = json.loads(marker.read_text(encoding="utf-8"))
                if value.get("cancelled") or (self.root / "STOP").exists():
                    return
                target = self.target(value["target"])
                self.run(["docker", "restart", target])
                value["manual_restarts"] += 1
                value["last_restart_at"] = now()
                value["StartedAt"] = self.inspect(target)["State"]["StartedAt"]
                write_json(marker, value)


def parser():
    result = argparse.ArgumentParser(description="Operator-only local incident injection and recovery")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    inject = commands.add_parser("inject")
    inject.add_argument("incident", nargs="?", choices=[*FLAGS, *INFRA])
    inject.add_argument("--combo", help="Comma-separated incidents to inject in sequence")
    inject.add_argument("--svc")
    inject.add_argument("--rate", default="100%")
    inject.add_argument("--delay", default="800ms")
    inject.add_argument("--loss", type=float, default=10)
    status = commands.add_parser("status")
    status.add_argument("--traffic-seconds", type=int, default=60)
    reset = commands.add_parser("reset")
    reset.add_argument("--timeout", type=int, default=90)
    commands.add_parser("up")
    commands.add_parser("down")
    commands.add_parser("build-netem")
    worker = commands.add_parser("_loop", help=argparse.SUPPRESS)
    worker.add_argument("marker")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        controller = Controller()
        if args.command == "list":
            result = {"incidents": [*FLAGS, *INFRA]}
        elif args.command == "inject":
            incidents = args.combo.split(",") if args.combo else ([args.incident] if args.incident else [])
            if not incidents or any(item not in FLAGS and item not in INFRA for item in incidents):
                raise FaultError("Choose an incident or --combo with known incident ids")
            result = {"runs": [controller.inject(item, args) for item in incidents]}
        elif args.command == "reset":
            result = controller.reset(timeout_s=args.timeout)
        elif args.command == "status":
            if not 0 <= args.traffic_seconds <= 60:
                raise FaultError("Traffic observation must be 0..60 seconds")
            result = controller.status(args.traffic_seconds)
        elif args.command == "up":
            result = controller.up()
        elif args.command == "down":
            with controller.lock():
                controller.cancel_loops(controller.state())
                controller.ensure_pristine()
                if controller.active.exists():
                    write_bytes(controller.active, controller.pristine.read_bytes())
                output = controller.compose("down")
                controller.override.unlink(missing_ok=True)
                write_json(controller.state_path, {"incidents": [], "flag_override": False, "last_down": now()})
            result = {"ok": True, "output": output.stdout + output.stderr}
        elif args.command == "build-netem":
            output = controller.run(["docker", "build", "-t", controller.config["netem_image"], "-f", str(controller.package / "netem" / "Dockerfile"), str(controller.package / "netem")], timeout=300)
            result = {"ok": True, "output": output.stdout + output.stderr}
        else:
            controller.loop(args.marker)
            return 0
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok", True) else 1
    except (FaultError, OSError, ValueError, KeyError, subprocess.SubprocessError, requests.RequestException) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
