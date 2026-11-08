"""Stdio MCP proxy that puts the gate in front of any MCP server.

holdpoint-proxy --policy P.yaml --state-dir DIR [--intent-file F] [--allow TOOL] -- COMMAND [ARG...]
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from fastmcp.server.server import create_proxy

from .approval import UNAPPROVABLE, Approvals
from .audit import AuditLog
from .gate import Decision, Gate
from .reviewer import reviewer_from_env
from .rules import validate as validate_rules

WAIT_POLL_SECONDS = 0.25
HOLD_TEXT = ("HELD: {tool} did not run. Reason: {reason} "
             "Nothing was changed. Tell the user what happened and what you need from them. Hold id: {hold_id}")


def _text(result) -> str:
    return " ".join(getattr(block, "text", "") for block in getattr(result, "content", []) or [])


def fingerprint(tool) -> str:
    definition = {"description": tool.description, "parameters": getattr(tool, "parameters", None),
                  "annotations": getattr(tool, "annotations", None)}
    return hashlib.sha256(json.dumps(definition, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class ToolPins:
    """Remembers each tool's definition when first seen, so a later change is noticed.

    Trust on first use: a definition that was already malicious when first seen is not caught.
    Read on every call, so `holdpoint accept-tools` takes effect in a running session.
    """

    def __init__(self, path):
        self.path = Path(path)

    def changed(self, tools) -> set[str]:
        pins = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        seen = {t.name: fingerprint(t) for t in tools}
        new = {name: value for name, value in seen.items() if name not in pins}
        if new:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({**pins, **new}, indent=1, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.path)
        return {name for name, value in seen.items() if name in pins and pins[name] != value}


def hint(annotations, snake: str, camel: str):
    # The MCP SDK is renaming these fields. Reading only one spelling would silently turn the check off.
    return getattr(annotations, snake if hasattr(annotations, snake) else camel, None)


def admits_it_changes_things(tool) -> bool:
    """A server's safety claims are untrusted, but its admission of danger only ever makes us stricter."""
    annotations = getattr(tool, "annotations", None)
    return (hint(annotations, "destructive_hint", "destructiveHint") is True
            or hint(annotations, "read_only_hint", "readOnlyHint") is False)


def redact(value, names: frozenset):
    if isinstance(value, dict):
        return {k: "[redacted]" if k in names else redact(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, names) for v in value]
    return value


class GateMiddleware(Middleware):
    def __init__(self, gate: Gate, approvals: Approvals, audit: AuditLog, pins: ToolPins | None = None,
                 redact_args: frozenset = frozenset(), wait_seconds: float = 0):
        self.gate, self.approvals, self.audit, self.pins = gate, approvals, audit, pins
        self.redact_args, self.wait_seconds = redact_args, wait_seconds
        self.trace: list[dict] = []
        # One call at a time, so a verdict always sees the full history.
        self.lock = asyncio.Lock()

    async def _decided_while_waiting(self, tool: str, args: dict, hold_id: str, inventory: dict):
        """Wait for a person. Once they approve, the gate decides again, so its limits and records still apply."""
        # ponytail: holds the session's lock, so one waiting call blocks the rest of this session. Clients have their own timeouts.
        deadline = time.monotonic() + self.wait_seconds
        while time.monotonic() < deadline:
            if self.approvals.was_denied(hold_id):
                return None
            if self.approvals.has_valid(tool, args):
                return await asyncio.to_thread(self.gate.decide, tool, args, inventory, list(self.trace))
            await asyncio.sleep(min(WAIT_POLL_SECONDS, self.wait_seconds))
        return None

    async def on_call_tool(self, context, call_next):
        tool = context.message.name
        args = dict(context.message.arguments or {})
        async with self.lock:
            tools = await context.fastmcp_context.fastmcp.list_tools()
            inventory = {t.name: {"description": t.description, "parameters": getattr(t, "parameters", None)}
                         for t in tools}
            logged_args = redact(args, self.redact_args)
            match = next((t for t in tools if t.name == tool), None)
            if self.pins is not None and tool in self.pins.changed(tools):
                decision = Decision(False, "pins", "this tool's definition changed since it was first seen. "
                                                   "Review it, then run: holdpoint accept-tools.")
            elif match is not None and not self.gate.is_commit(tool) and tool not in self.gate.allow \
                    and admits_it_changes_things(match):
                decision = Decision(False, "labels", "the policy labels this tool as safe, but the server says it can "
                                                     "change things. Check it, then relabel it commit.")
            else:
                decision = await asyncio.to_thread(self.gate.decide, tool, args, inventory, list(self.trace))
            self.audit.append(tool=tool, args=logged_args, allow=decision.allow, by=decision.by, reason=decision.reason,
                              usage=decision.usage)
            if not decision.allow:
                hold_id = self.approvals.record_hold(tool, args, decision.reason, decision.by)
                # Changed or mislabelled tools need a change to the setup, so a one-call approval cannot clear them.
                answer = None if decision.by in UNAPPROVABLE else await self._decided_while_waiting(tool, args, hold_id, inventory)
                if answer is None or not answer.allow:
                    reason = answer.reason if answer else decision.reason
                    if self.approvals.was_denied(hold_id):
                        reason = "a person rejected this call. Do not retry it."
                        self.audit.append(tool=tool, args=logged_args, allow=False, by="human", reason=f"rejected {hold_id}", usage=None)
                    elif answer is not None:
                        self.audit.append(tool=tool, args=logged_args, allow=False, by=answer.by, reason=answer.reason, usage=None)
                    raise ToolError(HOLD_TEXT.format(tool=tool, reason=reason, hold_id=hold_id))
                self.audit.append(tool=tool, args=logged_args, allow=True, by=answer.by, reason=answer.reason, usage=answer.usage)
            try:
                result = await call_next(context)
            except Exception as exc:
                self.trace.append({"tool": tool, "ok": False, "text": str(exc)})
                self.audit.append(tool=tool, by="outcome", allow=True, ok=False)
                raise
            ok = not getattr(result, "is_error", False)
            self.trace.append({"tool": tool, "ok": ok, "text": _text(result)})
            # The decision is logged before the call and the outcome after, so a crash leaves the intent on record.
            self.audit.append(tool=tool, by="outcome", allow=True, ok=ok)
            return result


def build(target, policy: dict, state_dir, intent: str | None = None, reviewer=None,
          allow: frozenset = frozenset(), key: bytes | None = None, redact_args: frozenset = frozenset(),
          wait_seconds: float = 0):
    validate_rules(policy)
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    approvals = Approvals(state, key)
    gate = Gate(policy, approvals, reviewer, intent, allow, state / "review_holds.json")
    proxy = create_proxy(target, name="holdpoint")
    proxy.add_middleware(GateMiddleware(gate, approvals, AuditLog(state / "audit.jsonl", key),
                                        ToolPins(state / "tool_pins.json"), redact_args, wait_seconds))
    return proxy


def downstream_env(environ) -> dict:
    """The signing key and reviewer credentials stay on the gate's side."""
    return {k: v for k, v in environ.items() if not k.startswith("HOLDPOINT_")}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--" not in argv:
        sys.exit("usage: holdpoint-proxy --policy P --state-dir D [--intent-file F] [--allow T] -- COMMAND [ARG...]")
    split = argv.index("--")
    downstream = argv[split + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--intent-file")
    parser.add_argument("--allow", action="append", default=[])
    parser.add_argument("--redact", action="append", default=[], help="an argument name to leave out of the audit log")
    parser.add_argument("--wait-seconds", type=float, default=0, help="how long a held call waits for a person before failing")
    a = parser.parse_args(argv[:split])
    with open(a.policy, encoding="utf-8") as f:
        policy = yaml.safe_load(f) or {}
    intent = Path(a.intent_file).read_text(encoding="utf-8") if a.intent_file else None
    key = os.environ.get("HOLDPOINT_KEY")
    transport = StdioTransport(downstream[0], downstream[1:], env=downstream_env(os.environ), keep_alive=True)
    proxy = build(Client(transport), policy, a.state_dir, intent, reviewer_from_env(),
                  frozenset(a.allow), key.encode("utf-8") if key else None, frozenset(a.redact), a.wait_seconds)
    proxy.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
