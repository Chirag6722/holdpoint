"""Stdio MCP proxy that puts the gate in front of any MCP server.

holdpoint-proxy --policy P.yaml --state-dir DIR [--intent-file F] [--allow TOOL] -- COMMAND [ARG...]
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from fastmcp.server.server import create_proxy

from .approval import Approvals
from .audit import AuditLog
from .gate import Gate
from .reviewer import reviewer_from_env

HOLD_TEXT = ("HELD: {tool} did not run. Reason: {reason} "
             "Nothing was changed. Tell the user what happened and what you need from them. Hold id: {hold_id}")


def _text(result) -> str:
    return " ".join(getattr(block, "text", "") for block in getattr(result, "content", []) or [])


class GateMiddleware(Middleware):
    def __init__(self, gate: Gate, approvals: Approvals, audit: AuditLog):
        self.gate, self.approvals, self.audit = gate, approvals, audit
        self.trace: list[dict] = []
        # One call at a time, so a verdict always sees the full history.
        self.lock = asyncio.Lock()

    async def on_call_tool(self, context, call_next):
        tool = context.message.name
        args = dict(context.message.arguments or {})
        async with self.lock:
            tools = await context.fastmcp_context.fastmcp.list_tools()
            inventory = {t.name for t in tools}
            decision = await asyncio.to_thread(self.gate.decide, tool, args, inventory, list(self.trace))
            self.audit.append(tool=tool, args=args, allow=decision.allow, by=decision.by, reason=decision.reason,
                              usage=decision.usage)
            if not decision.allow:
                hold_id = self.approvals.record_hold(tool, args, decision.reason)
                raise ToolError(HOLD_TEXT.format(tool=tool, reason=decision.reason, hold_id=hold_id))
            try:
                result = await call_next(context)
            except Exception as exc:
                self.trace.append({"tool": tool, "ok": False, "text": str(exc)})
                raise
            ok = not getattr(result, "is_error", False)
            self.trace.append({"tool": tool, "ok": ok, "text": _text(result)})
            return result


def build(target, policy: dict, state_dir, intent: str | None = None, reviewer=None,
          allow: frozenset = frozenset(), key: bytes | None = None):
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    approvals = Approvals(state, key)
    gate = Gate(policy, approvals, reviewer, intent, allow)
    proxy = create_proxy(target, name="holdpoint")
    proxy.add_middleware(GateMiddleware(gate, approvals, AuditLog(state / "audit.jsonl")))
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
    a = parser.parse_args(argv[:split])
    with open(a.policy, encoding="utf-8") as f:
        policy = yaml.safe_load(f) or {}
    intent = Path(a.intent_file).read_text(encoding="utf-8") if a.intent_file else None
    key = os.environ.get("HOLDPOINT_KEY")
    transport = StdioTransport(downstream[0], downstream[1:], env=downstream_env(os.environ), keep_alive=True)
    proxy = build(Client(transport), policy, a.state_dir, intent, reviewer_from_env(),
                  frozenset(a.allow), key.encode("utf-8") if key else None)
    proxy.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
