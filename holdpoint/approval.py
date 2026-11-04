"""Human approvals: signed, bound to one exact call, single use, expiring.

The agent reaches tools only through the proxy, so it can neither read this
directory nor hold the signing key.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path


def call_hash(tool: str, args: dict) -> str:
    canonical = json.dumps({"tool": tool, "args": args}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Approvals:
    def __init__(self, state_dir, key: bytes | None):
        self.key = key
        self.pending = Path(state_dir) / "pending"
        self.tokens = Path(state_dir) / "tokens"
        self.pending.mkdir(parents=True, exist_ok=True)
        self.tokens.mkdir(parents=True, exist_ok=True)

    def _mac(self, hold_id: str, digest: str, expires: float) -> str:
        msg = f"{hold_id}|{digest}|{expires!r}".encode()
        return hmac.new(self.key, msg, hashlib.sha256).hexdigest()

    def record_hold(self, tool: str, args: dict, reason: str) -> str:
        hold_id = secrets.token_hex(8)
        record = {"hold_id": hold_id, "tool": tool, "args": args, "reason": reason, "at": time.time()}
        (self.pending / f"{hold_id}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        return hold_id

    def list_holds(self) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.pending.glob("*.json"))]

    def approve(self, hold_id: str, ttl_seconds: float, now: float | None = None) -> None:
        if self.key is None:
            raise ValueError("no signing key configured")
        record = json.loads((self.pending / f"{hold_id}.json").read_text(encoding="utf-8"))
        digest = call_hash(record["tool"], record["args"])
        expires = (time.time() if now is None else now) + ttl_seconds
        token = {"hold_id": hold_id, "digest": digest, "expires": expires,
                 "mac": self._mac(hold_id, digest, expires)}
        (self.tokens / f"{hold_id}.json").write_text(json.dumps(token), encoding="utf-8")

    def consume(self, tool: str, args: dict, now: float | None = None) -> str | None:
        """Spend a valid token for this exact call. Returns its hold id, or None."""
        if self.key is None:
            return None
        now = time.time() if now is None else now
        digest = call_hash(tool, args)
        for path in sorted(self.tokens.glob("*.json")):
            try:
                t = json.loads(path.read_text(encoding="utf-8"))
                good = hmac.compare_digest(t["mac"], self._mac(t["hold_id"], t["digest"], t["expires"]))
                match = t["digest"] == digest
                fresh = float(t["expires"]) > now
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if good and match and fresh:
                try:
                    # Rename is atomic, so only one caller can spend the token.
                    os.replace(path, path.with_suffix(".used"))
                except OSError:
                    continue
                return t["hold_id"]
        return None
