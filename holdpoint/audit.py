"""Append-only JSONL log where each line commits to the previous line's hash."""
import hashlib
import json
import os

GENESIS = "0" * 64


def _digest(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path):
        self.path = path
        self.prev = GENESIS
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    self.prev = json.loads(line)["hash"]

    def append(self, **event) -> None:
        h = _digest(self.prev, event)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": event, "prev": self.prev, "hash": h}, sort_keys=True) + "\n")
        self.prev = h


def verify(path) -> tuple[bool, int]:
    """Return (intact, lines checked). Stops at the first broken line."""
    prev, n = GENESIS, 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                ok = rec["prev"] == prev and rec["hash"] == _digest(prev, rec["event"])
            except (ValueError, KeyError, TypeError):
                ok = False
            if not ok:
                return False, n
            prev, n = rec["hash"], n + 1
    return True, n
