"""Narrow local executors; callers must pass the approval boundary first."""
import json
import os
import subprocess
import time
import requests
from agent.policy import SERVICES
from .flags import Switches
from .safety import Blocked


class LocalExecutor:
    def __init__(self, stop_path):
        self.stop_path = stop_path
        self.switches = Switches(self.inspect)
        self.load_url = "http://localhost:8080/loadgen"

    def check_stop(self):
        if self.stop_path.exists():
            raise Blocked("STOP_LATCHED", 423)

    def command(self, arguments, mutation=False):
        if mutation:
            self.check_stop()
        env = dict(os.environ)
        env.setdefault("DOCKER_HOST", "tcp://localhost:2375")
        proc = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        started = time.monotonic()
        while True:
            try:
                if mutation:
                    self.check_stop()
                out, err = proc.communicate(timeout=.2)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started < 45:
                    continue
                proc.kill()
                proc.communicate()
                raise Blocked("EXECUTOR_TIMEOUT", 409)
            except Blocked:
                proc.kill()
                proc.communicate()
                raise
        if proc.returncode:
            # Raw backend output can disclose configuration; retain only a code.
            raise Blocked("EXECUTOR_COMMAND_FAILED", 409)
        return out.decode("utf-8")

    def inspect(self, service):
        return json.loads(self.command(["docker", "inspect", service]))[0]

    def load_state(self):
        response = requests.get(self.load_url + "/stats/requests", timeout=10)
        response.raise_for_status()
        value = response.json()
        # Locust stats do not expose spawn rate; refuse to guess rollback state.
        response = requests.get(self.load_url + "/", timeout=10)
        response.raise_for_status()
        import re
        match = re.search(r'"spawn_rate"\s*:\s*([\d.]+)', response.text)
        if not match:
            raise Blocked("LOAD_ROLLBACK_STATE_UNAVAILABLE", 409)
        return {"users": int(value["user_count"]), "spawn_rate": float(match[1])}

    def snapshot(self, plan):
        rows = {s: self.inspect(s) for s in SERVICES}
        containers = {s: {"id": r["Id"], "status": r["State"]["Status"],
                         "started": r["State"].get("StartedAt"),
                         "limits": {k: r["HostConfig"].get(k) for k in ("NanoCpus", "Memory", "MemorySwap")}}
                      for s, r in rows.items()}
        switches = self.switches.snapshot(plan["target"] if plan["action"] == "toggle_flag" else None)
        load = self.load_state() if plan["action"] == "throttle_load" else None
        return {"containers": containers, "switches": switches, "load": load}

    def execute(self, plan, before):
        self.check_stop()
        operation, target = plan["action"], plan["target"]
        if operation == "restart_service":
            self.command(["docker", "restart", target], mutation=True)
            if self.inspect(target)["State"]["Status"] != "running":
                raise Blocked("RESTART_READBACK_FAILED", 409)
        elif operation == "toggle_flag":
            self.switches.apply(target)
        elif operation == "throttle_load":
            self.set_load(plan["parameters"])
        else:
            raise Blocked("FORBIDDEN_OPERATION")
        return {"applied": True}

    def set_load(self, values):
        self.check_stop()
        response = requests.post(self.load_url + "/swarm",
                                 data={"user_count": values["users"], "spawn_rate": values["spawn_rate"]}, timeout=10)
        response.raise_for_status()
        if not response.json().get("success"):
            raise Blocked("LOAD_CHANGE_FAILED", 409)

    def rollback(self, plan, before):
        self.check_stop()
        if plan["action"] == "restart_service":
            return {"restored": False, "reason": "Restart cannot restore interrupted requests or prior process state."}
        if plan["action"] == "toggle_flag":
            self.switches.apply(plan["target"], before["switches"]["prior"])
        else:
            self.set_load(before["load"])
        return {"restored": True}
