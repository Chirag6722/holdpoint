"""Human approvals: signed, bound to one exact call, single use, expiring.

The agent reaches tools only through the proxy, so it can neither read this
directory nor hold the signing key.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path

HOLD_ID = re.compile(r"[0-9a-f]{16}")


def call_hash(tool: str, args: dict) -> str:
    canonical = json.dumps({"tool": tool, "args": args}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Approvals:
    def __init__(self, state_dir, key: bytes | None):
        self.key = key
        # Holds and the log contain tool arguments, so only this user may read them.
        Path(state_dir).mkdir(parents=True, exist_ok=True)
        Path(state_dir).chmod(0o700)
        self.pending = Path(state_dir) / "pending"
        self.tokens = Path(state_dir) / "tokens"
        self.pending.mkdir(parents=True, exist_ok=True)
        self.tokens.mkdir(parents=True, exist_ok=True)

    def _mac(self, hold_id: str, digest: str, expires: float) -> str:
        msg = f"{hold_id}|{digest}|{expires!r}".encode()
        return hmac.new(self.key, msg, hashlib.sha256).hexdigest()

    def _hold_mac(self, hold_id: str, tool: str, args: dict) -> str:
        msg = f"hold|{hold_id}|{call_hash(tool, args)}".encode()
        return hmac.new(self.key, msg, hashlib.sha256).hexdigest()

    def record_hold(self, tool: str, args: dict, reason: str) -> str:
        hold_id = secrets.token_hex(8)
        record = {"hold_id": hold_id, "tool": tool, "args": args, "reason": reason, "at": time.time()}
        if self.key is not None:
            # A person approves what this file says, so the file must be proven unchanged.
            record["mac"] = self._hold_mac(hold_id, tool, args)
        (self.pending / f"{hold_id}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        return hold_id

    def list_holds(self) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.pending.glob("*.json"))]

    def approve(self, hold_id: str, ttl_seconds: float, now: float | None = None) -> None:
        if self.key is None:
            raise ValueError("no signing key configured")
        if not HOLD_ID.fullmatch(hold_id):
            raise ValueError("not a hold id")
        path = self.pending / f"{hold_id}.json"
        if not path.exists():
            raise ValueError("no pending hold with that id; it may already be used")
        record = json.loads(path.read_text(encoding="utf-8"))
        if not hmac.compare_digest(str(record.get("mac")), self._hold_mac(hold_id, record["tool"], record["args"])):
            raise ValueError("this hold record was changed or signed with another key; refusing to approve it")
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
                hold = self.pending / f"{t['hold_id']}.json"
                if hold.exists():
                    os.replace(hold, hold.with_suffix(".used"))
                return t["hold_id"]
        return None
