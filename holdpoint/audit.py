"""Append-only JSONL log where each line commits to the previous line's hash.

With a key the chain is signed and a signed head records its length, so rewriting or cutting
the log needs the key. Without one, the chain only catches accidental or partial edits.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path

GENESIS = "0" * 64


def _log_key(key: bytes | None) -> bytes | None:
    # Approvals sign with the same secret, so the log gets its own derived key.
    return hmac.new(key, b"holdpoint-audit-log", hashlib.sha256).digest() if key else None


def _digest(prev: str, body: dict, log_key: bytes | None = None) -> str:
    data = (prev + json.dumps(body, sort_keys=True)).encode("utf-8")
    return hmac.new(log_key, data, hashlib.sha256).hexdigest() if log_key else hashlib.sha256(data).hexdigest()


def _head_mac(log_key: bytes, count: int, last: str) -> str:
    return hmac.new(log_key, f"head|{count}|{last}".encode(), hashlib.sha256).hexdigest()


def _head_path(path) -> Path:
    return Path(path).with_suffix(".head")


class AuditLog:
    def __init__(self, path, key: bytes | None = None):
        self.path, self.log_key = path, _log_key(key)
        self.prev, self.count = GENESIS, 0
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    self.prev, self.count = json.loads(line)["hash"], self.count + 1

    def append(self, **event) -> None:
        h = _digest(self.prev, event, self.log_key)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": event, "prev": self.prev, "hash": h}, sort_keys=True) + "\n")
        self.prev, self.count = h, self.count + 1
        if self.log_key:
            head = _head_path(self.path)
            tmp = head.with_suffix(".tmp")
            tmp.write_text(json.dumps({"count": self.count, "hash": h,
                                       "mac": _head_mac(self.log_key, self.count, h)}), encoding="utf-8")
            os.replace(tmp, head)


def _head_matches(path, log_key: bytes, count: int, last: str) -> bool:
    try:
        head = json.loads(_head_path(path).read_text(encoding="utf-8"))
        return (head["count"] == count and head["hash"] == last
                and hmac.compare_digest(head["mac"], _head_mac(log_key, count, last)))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def verify(path, key: bytes | None = None, expect: str | None = None) -> tuple[bool, int]:
    """Return (intact, lines checked). Stops at the first broken line.

    `expect` is a hash saved earlier, outside this directory. It must still be in the chain,
    which catches a whole log being deleted or rolled back together with its head.
    """
    log_key = _log_key(key)
    prev, n, seen = GENESIS, 0, False
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    ok = rec["prev"] == prev and rec["hash"] == _digest(prev, rec["event"], log_key)
                except (ValueError, KeyError, TypeError):
                    ok = False
                if not ok:
                    return False, n
                prev, n = rec["hash"], n + 1
                seen = seen or prev == expect
    if expect and not seen:
        return False, n
    if log_key and n and not _head_matches(path, log_key, n, prev):
        return False, n
    if not n and _head_path(path).exists():
        return False, n
    return True, n


def latest_hash(path) -> str:
    log = AuditLog(path)
    return log.prev
