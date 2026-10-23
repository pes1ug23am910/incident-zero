"""Shared fail-closed errors, hashes and cross-process exclusion."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os


class Blocked(Exception):
    def __init__(self, code, status=403, message=None):
        self.code, self.status = code, status
        super().__init__(message or code)

    def payload(self):
        return {"decision": "BLOCK", "reason_codes": [self.code], "detail": str(self)}


def now():
    return datetime.now(timezone.utc).isoformat()


def diagnosis_is_current(report, observed_at):
    """Share one age boundary between queue visibility and action authority."""
    try:
        diagnosed = datetime.fromisoformat(report['diagnosed_at'])
        return diagnosed.utcoffset() is not None and -45 <= observed_at - diagnosed.timestamp() <= 600
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return False


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0)
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise Blocked("MUTATION_IN_FLIGHT", 409) from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
