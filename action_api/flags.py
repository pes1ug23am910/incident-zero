"""The sole hands-side service-to-flag mapping and configuration access.

These reads are not diagnosis: they bind approvals to world state and retain
the previous variant for rollback. No variant or flag name enters agent
prompts, reports or the action journal. The operator's mounted overlay is
required; the official demo source is never rewritten by this executor.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from .safety import Blocked

MAPPING = {
    "payment": {"paymentFailure": "off", "paymentUnreachable": "off"},
    "cart": {"cartFailure": "off"},
    "product-catalog": {"productCatalogFailure": "off"},
    "recommendation": {"recommendationCacheFailure": "off"},
    "ad": {"adHighCpu": "off", "adManualGc": "off", "adFailure": "off"},
}


class Switches:
    def __init__(self, inspect, path=None):
        self.inspect = inspect
        configured = path or os.environ.get("INCIDENT_ZERO_SWITCH_FILE")
        self.path = Path(configured) if configured else None

    def document(self):
        mounts = self.inspect("flagd").get("Mounts", [])
        def local(source):
            source = source.replace("\\", "/").lower().rstrip("/")
            return re.sub(r"^/(?:run/desktop/mnt/host|host_mnt)/([a-z])(?=/)", r"\1:", source)
        candidates = []
        for mount in mounts:
            destination = mount.get('Destination')
            if destination == '/etc/flagd':
                candidates.append(Path(local(mount['Source'])) / 'demo.flagd.json')
            elif destination == '/etc/flagd/demo.flagd.json':
                candidates.append(Path(local(mount['Source'])))
        if self.path is None and len(candidates) == 1:
            self.path = candidates[0]
        if self.path is None or not any(p.resolve() == self.path.resolve() for p in candidates):
            raise Blocked("SWITCH_MOUNT_MISMATCH", 409)
        return json.loads(self.path.read_text(encoding="utf-8"))

    def snapshot(self, service=None):
        doc = self.document()
        prior = {}
        if service is not None:
            self.require_overlay()
            if service not in MAPPING:
                raise Blocked("UNSUPPORTED_SWITCH_TARGET")
            for name, normal in MAPPING[service].items():
                entry = doc["flags"][name]
                if normal not in entry["variants"]:
                    raise Blocked("UNSUPPORTED_SWITCH_VARIANT")
                prior[name] = entry["defaultVariant"]
        return {"sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(), "prior": prior}

    def apply(self, service, prior=None):
        doc = self.document()
        self.require_overlay()
        values = prior if prior is not None else MAPPING[service]
        if set(values) != set(MAPPING[service]):
            raise Blocked("INVALID_ROLLBACK_STATE")
        for name, value in values.items():
            if value not in doc["flags"][name]["variants"]:
                raise Blocked("UNSUPPORTED_SWITCH_VARIANT")
            doc["flags"][name]["defaultVariant"] = value
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
        actual = self.document()
        if any(actual["flags"][name]["defaultVariant"] != value for name, value in values.items()):
            raise Blocked("SWITCH_READBACK_FAILED", 409)

    def require_overlay(self):
        if '/.state/flags/' not in self.path.as_posix().lower():
            raise Blocked('OPERATOR_OVERLAY_REQUIRED', 403)
